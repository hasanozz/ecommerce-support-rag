from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import inspect, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models import (
    Feedback,
    Message,
    RagRun,
    SimilarSolution,
    SimilarSolutionImpression,
    User,
)
from ..schemas.feedback import (
    FeedbackAnalyticsResponse,
    FeedbackCategoryBreakdown,
    FeedbackResponse,
    MessageFeedbackRequest,
    RecentFeedbackItem,
    SimilarFeedbackRequest,
)
from ..services.auth import get_current_user
from ..services.privacy import request_ip_hash
from ..services.rate_limit import rate_limiter
from ..services.similar import SimilarSolutionService
from ..services.tickets import TicketService
from ..services.email import process_outbox_once


router = APIRouter(prefix="/api", tags=["feedback"])


def apply_vote(target, value: str) -> None:
    if value == "HELPFUL":
        target.helpful_count += 1
    else:
        target.unhelpful_count += 1


def rate(part: int, total: int) -> float:
    if not total:
        return 0.0
    return round(part / total, 4)


def normalize_feedback_value(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    return normalized if normalized in {"HELPFUL", "UNHELPFUL"} else "UNHELPFUL"


def normalize_sources(value: object) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


async def feedback_comment_column_exists(session: AsyncSession) -> bool:
    return await session.run_sync(
        lambda sync_session: any(
            column["name"] == "comment"
            for column in inspect(sync_session.bind).get_columns("feedback")
        )
    )


# Keep this route independent from UI concerns. It must return a stable 200 JSON
# shape for dashboard smoke checks, including fresh databases with no feedback.
@router.get("/admin/feedback-analytics", response_model=FeedbackAnalyticsResponse)
async def admin_feedback_analytics(
    limit: int = 10,
    session: AsyncSession = Depends(get_db),
) -> FeedbackAnalyticsResponse:
    limit = max(1, min(limit, 50))
    base_filter = Feedback.message_id.is_not(None)
    comment_expr = (
        Feedback.comment
        if await feedback_comment_column_exists(session)
        else literal(None).label("comment")
    )

    analytics_rows = (
        await session.execute(
            select(Feedback.value, Message.category, Message.confidence_score)
            .outerjoin(Message, Feedback.message_id == Message.id)
            .where(base_filter)
        )
    ).all()
    total_feedback = len(analytics_rows)
    helpful_count = sum(
        1 for row in analytics_rows if normalize_feedback_value(row.value) == "HELPFUL"
    )
    unhelpful_count = sum(
        1
        for row in analytics_rows
        if normalize_feedback_value(row.value) == "UNHELPFUL"
    )

    confidence_scores = [
        float(row.confidence_score)
        for row in analytics_rows
        if row.confidence_score is not None
    ]
    average_confidence_score = (
        round(sum(confidence_scores) / len(confidence_scores), 4)
        if confidence_scores
        else None
    )

    categories: dict[str, dict[str, int]] = {}
    for row in analytics_rows:
        category = (row.category or "").strip() or "Bilinmiyor"
        bucket = categories.setdefault(
            category, {"helpful_count": 0, "unhelpful_count": 0, "total": 0}
        )
        bucket["total"] += 1
        if normalize_feedback_value(row.value) == "HELPFUL":
            bucket["helpful_count"] += 1
        else:
            bucket["unhelpful_count"] += 1

    category_breakdown = [
        FeedbackCategoryBreakdown(
            category=category,
            helpful_count=counts["helpful_count"],
            unhelpful_count=counts["unhelpful_count"],
            total=counts["total"],
            helpful_rate=rate(counts["helpful_count"], counts["total"]),
        )
        for category, counts in sorted(
            categories.items(), key=lambda item: item[1]["total"], reverse=True
        )
    ]
    recent_rows = (
        await session.execute(
            select(
                Feedback.message_id,
                Feedback.value,
                comment_expr.label("feedback_comment"),
                Feedback.created_at,
                Feedback.user_id,
                Message.safe_content,
                Message.canonical_query,
                Message.category,
                Message.confidence_score,
                Message.sources,
                RagRun.model_name,
                RagRun.total_tokens,
                RagRun.rewritten_query,
            )
            .outerjoin(Message, Feedback.message_id == Message.id)
            .outerjoin(RagRun, RagRun.assistant_message_id == Message.id)
            .where(base_filter)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
    ).all()
    recent_feedback = [
        RecentFeedbackItem(
            message_id=message_id,
            ai_answer=safe_content or "",
            canonical_query=(
                canonical_query
                if canonical_query
                else rewritten_query
            ),
            category=(
                category if category else "Bilinmiyor"
            ),
            confidence_score=confidence_score,
            sources=normalize_sources(sources),
            feedback_value=normalize_feedback_value(value),
            feedback_comment=feedback_comment,
            feedback_created_at=created_at,
            user_id=user_id,
            model_name=model_name,
            total_tokens=total_tokens,
        )
        for (
            message_id,
            value,
            feedback_comment,
            created_at,
            user_id,
            safe_content,
            canonical_query,
            category,
            confidence_score,
            sources,
            model_name,
            total_tokens,
            rewritten_query,
        ) in recent_rows
    ]
    return FeedbackAnalyticsResponse(
        total_feedback=total_feedback,
        helpful_count=helpful_count,
        unhelpful_count=unhelpful_count,
        helpful_rate=rate(helpful_count, total_feedback),
        unhelpful_rate=rate(unhelpful_count, total_feedback),
        average_confidence_score=average_confidence_score,
        category_breakdown=category_breakdown,
        recent_feedback=recent_feedback,
    )


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse)
async def message_feedback(
    message_id: int,
    payload: MessageFeedbackRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackResponse:
    settings = get_settings()
    ip_hash = request_ip_hash(request)
    rate_limiter.check(
        f"feedback:user:{user.id}",
        settings.feedback_rate_limit,
        settings.feedback_rate_window_seconds,
    )
    rate_limiter.check(
        f"feedback:ip:{ip_hash}",
        settings.feedback_rate_limit,
        settings.feedback_rate_window_seconds,
    )
    message = await session.scalar(
        select(Message)
        .join(Message.conversation)
        .where(
            Message.id == message_id,
            Message.role == "ASSISTANT",
            Message.conversation.has(user_id=user.id),
        )
    )
    if message is None:
        raise HTTPException(404, "Cevap bulunamadı.")
    feedback = Feedback(
        user_id=user.id,
        message_id=message.id,
        value=payload.value,
        comment=(payload.comment or payload.note or "").strip() or None,
        ip_hash=ip_hash,
    )
    session.add(feedback)
    apply_vote(message, payload.value)
    ticket_id = None
    try:
        if payload.value == "UNHELPFUL" and payload.open_ticket:
            ticket = await TicketService(settings).create(
                session, user, message, payload.note.strip()
            )
            ticket_id = ticket.id
        rag_run = await session.scalar(
            select(RagRun).where(RagRun.assistant_message_id == message.id)
        )
        await SimilarSolutionService().upsert_from_answer(
            session,
            rag_run.rewritten_query if rag_run else message.safe_content,
            message.safe_content,
            message.category or "GENEL_DESTEK",
            message.helpful_count,
            message.unhelpful_count,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Bu cevap için daha önce geri bildirim verdiniz.") from exc
    if ticket_id is not None:
        background_tasks.add_task(process_outbox_once)
    return FeedbackResponse(
        status="Teşekkürler, geri bildiriminiz kaydedildi.",
        ticket_id=ticket_id,
    )


@router.post(
    "/similar-solutions/{solution_id}/feedback",
    response_model=FeedbackResponse,
)
async def similar_feedback(
    solution_id: int,
    payload: SimilarFeedbackRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackResponse:
    settings = get_settings()
    ip_hash = request_ip_hash(request)
    rate_limiter.check(
        f"feedback:ip:{ip_hash}",
        settings.feedback_rate_limit,
        settings.feedback_rate_window_seconds,
    )
    solution = await session.get(SimilarSolution, solution_id)
    has_impression = await session.scalar(
        select(SimilarSolutionImpression.id).where(
            SimilarSolutionImpression.similar_solution_id == solution_id,
            SimilarSolutionImpression.user_id == user.id,
        )
    )
    if solution is None or has_impression is None:
        raise HTTPException(404, "Benzer çözüm bulunamadı.")
    session.add(
        Feedback(
            user_id=user.id,
            similar_solution_id=solution.id,
            value=payload.value,
            ip_hash=ip_hash,
        )
    )
    apply_vote(solution, payload.value)
    total = solution.helpful_count + solution.unhelpful_count
    solution.success_rate = solution.helpful_count / total if total else 0.0
    await SimilarSolutionService(settings=settings).refresh_publication(
        session, solution
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Bu çözüm için daha önce oy verdiniz.") from exc
    return FeedbackResponse(status="Benzer çözüm geri bildirimi kaydedildi.")
