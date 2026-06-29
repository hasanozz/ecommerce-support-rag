from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import case, func, select
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
from ..services.auth import get_current_user, require_admin
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


@router.get("/admin/feedback-analytics", response_model=FeedbackAnalyticsResponse)
async def admin_feedback_analytics(
    limit: int = 10,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> FeedbackAnalyticsResponse:
    limit = max(1, min(limit, 50))
    base_filter = Feedback.message_id.is_not(None)
    total_feedback = (
        await session.scalar(select(func.count(Feedback.id)).where(base_filter))
    ) or 0
    helpful_count = (
        await session.scalar(
            select(func.count(Feedback.id)).where(
                base_filter,
                Feedback.value == "HELPFUL",
            )
        )
    ) or 0
    unhelpful_count = (
        await session.scalar(
            select(func.count(Feedback.id)).where(
                base_filter,
                Feedback.value == "UNHELPFUL",
            )
        )
    ) or 0
    average_confidence_score = await session.scalar(
        select(func.avg(Message.confidence_score))
        .join(Feedback, Feedback.message_id == Message.id)
        .where(base_filter, Message.confidence_score.is_not(None))
    )
    category_rows = (
        await session.execute(
            select(
                func.coalesce(Message.category, "GENEL").label("category"),
                func.sum(case((Feedback.value == "HELPFUL", 1), else_=0)).label(
                    "helpful_count"
                ),
                func.sum(case((Feedback.value == "UNHELPFUL", 1), else_=0)).label(
                    "unhelpful_count"
                ),
                func.count(Feedback.id).label("total"),
            )
            .join(Message, Feedback.message_id == Message.id)
            .where(base_filter)
            .group_by(func.coalesce(Message.category, "GENEL"))
            .order_by(func.count(Feedback.id).desc())
        )
    ).all()
    category_breakdown = [
        FeedbackCategoryBreakdown(
            category=row.category,
            helpful_count=int(row.helpful_count or 0),
            unhelpful_count=int(row.unhelpful_count or 0),
            total=int(row.total or 0),
            helpful_rate=rate(int(row.helpful_count or 0), int(row.total or 0)),
        )
        for row in category_rows
    ]
    recent_rows = (
        await session.execute(
            select(
                Feedback,
                Message,
                RagRun.model_name,
                RagRun.total_tokens,
            )
            .join(Message, Feedback.message_id == Message.id)
            .outerjoin(RagRun, RagRun.assistant_message_id == Message.id)
            .where(base_filter)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
    ).all()
    recent_feedback = [
        RecentFeedbackItem(
            message_id=message.id,
            ai_answer=message.safe_content,
            canonical_query=message.canonical_query,
            category=message.category,
            confidence_score=message.confidence_score,
            sources=message.sources or [],
            feedback_value=feedback.value,
            feedback_created_at=feedback.created_at,
            user_id=feedback.user_id,
            model_name=model_name,
            total_tokens=total_tokens,
        )
        for feedback, message, model_name, total_tokens in recent_rows
    ]
    return FeedbackAnalyticsResponse(
        total_feedback=total_feedback,
        helpful_count=helpful_count,
        unhelpful_count=unhelpful_count,
        helpful_rate=rate(helpful_count, total_feedback),
        unhelpful_rate=rate(unhelpful_count, total_feedback),
        average_confidence_score=(
            round(float(average_confidence_score), 4)
            if average_confidence_score is not None
            else None
        ),
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
