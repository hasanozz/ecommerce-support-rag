from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
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
    FeedbackResponse,
    MessageFeedbackRequest,
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
