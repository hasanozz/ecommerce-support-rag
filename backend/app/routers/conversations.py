from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..database import get_db
from ..models import Conversation, Feedback, Message, User
from ..schemas.conversation import (
    AssistantAnswerResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    MessageCreate,
    MessageResponse,
    SimilarSolutionResponse,
    SourceResponse,
)
from ..services.auth import get_current_user
from ..services.pipeline import SupportPipeline
from ..services.privacy import request_ip_hash
from ..services.rate_limit import rate_limiter
from ..services.security import sanitize_query


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


async def owned_conversation(
    session: AsyncSession, conversation_id: int, user_id: int
) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise HTTPException(404, "Görüşme bulunamadı.")
    return conversation


@router.post("", response_model=ConversationSummary)
async def create_conversation(
    payload: ConversationCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    conversation = Conversation(user_id=user.id, title=payload.title.strip() or "Yeni görüşme")
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    return list(
        (
            await session.scalars(
                select(Conversation)
                .where(Conversation.user_id == user.id)
                .order_by(Conversation.updated_at.desc())
            )
        ).all()
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def conversation_detail(
    conversation_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationDetail:
    conversation = await session.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if conversation is None:
        raise HTTPException(404, "Görüşme bulunamadı.")
    messages = sorted(conversation.messages, key=lambda item: item.id)
    feedback_rows = (
        await session.execute(
            select(Feedback.message_id, Feedback.value).where(
                Feedback.user_id == user.id,
                Feedback.message_id.in_([item.id for item in messages]),
            )
        )
    ).all()
    feedback_map = {message_id: value for message_id, value in feedback_rows}
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        status=conversation.status,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageResponse(
                id=item.id,
                role=item.role,
                content=item.safe_content,
                canonical_query=item.canonical_query,
                category=item.category,
                confidence=item.confidence,
                sources=item.sources,
                helpful_count=item.helpful_count,
                unhelpful_count=item.unhelpful_count,
                user_feedback=feedback_map.get(item.id),
                created_at=item.created_at,
            )
            for item in messages
        ],
    )


@router.post("/{conversation_id}/messages", response_model=AssistantAnswerResponse)
async def send_message(
    conversation_id: int,
    payload: MessageCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssistantAnswerResponse:
    settings = get_settings()
    ip_hash = request_ip_hash(request)
    rate_limiter.check(
        f"chat:user:{user.id}", settings.chat_rate_limit, settings.chat_rate_window_seconds
    )
    rate_limiter.check(
        f"chat:ip:{ip_hash}", settings.chat_rate_limit, settings.chat_rate_window_seconds
    )
    safe_query = sanitize_query(payload.message, settings)
    conversation = await owned_conversation(session, conversation_id, user.id)
    frontend_context = payload.model_dump(
        include={
            "current_product_id",
            "current_order_id",
            "current_cart_id",
            "current_return_id",
            "current_payment_id",
            "page_context",
        },
        exclude_none=True,
    )
    assistant, canonical, grouped, similar, classification = await SupportPipeline(settings).run(
        session,
        conversation,
        user,
        safe_query,
        ip_hash,
        frontend_context=frontend_context,
    )
    debug_trace = (
        assistant.security_metadata.get("debug", {})
        if isinstance(assistant.security_metadata, dict)
        else {}
    )
    return AssistantAnswerResponse(
        assistant_message_id=assistant.id,
        answer=assistant.safe_content,
        canonical_query=canonical,
        category=classification.category,
        subcategory=classification.subcategory,
        domain=classification.domain,
        intent=classification.intent,
        expected_action=classification.expected_action,
        requested_information=classification.requested_information
        or ([classification.requested_info] if classification.requested_info else []),
        answer_source=str(debug_trace.get("answer_source") or "").strip() or None,
        sources=[
            SourceResponse(
                doc_id=item.doc_id,
                title=item.title,
                category=item.category,
                subcategory=item.subcategory,
                best_score=item.best_score,
                matched_sections=item.matched_sections,
                combined_context=item.combined_context,
            )
            for item in grouped
        ],
        confidence=assistant.confidence,
        confidence_score=assistant.confidence_score,
        priority=classification.priority,
        ticket_available=True,
        ticket_recommended=classification.expected_action == "CREATE_TICKET",
        similar_solutions=[
            SimilarSolutionResponse(
                id=solution.id,
                canonical_question=solution.canonical_question,
                safe_answer=solution.safe_answer,
                similarity_score=score,
                helpful_count=solution.helpful_count,
                view_count=view_count + 1,
                success_rate=solution.success_rate,
            )
            for solution, score, view_count in similar
        ],
    )
