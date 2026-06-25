from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..models import (
    Conversation,
    EmailOutbox,
    Message,
    Ticket,
    TicketStatusHistory,
    User,
)
from .email import EmailService


DEPARTMENTS = {
    "SIPARIS": "Sipariş",
    "IADE": "İade",
    "ODEME": "Ödeme",
    "KARGO_TESLIMAT": "Lojistik",
    "HESAP_GUVENLIK": "Hesap Güvenliği",
    "KAMPANYA_PUAN": "Kampanya",
    "GENEL_DESTEK": "Genel Destek",
}


class TicketService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.email = EmailService(self.settings)

    async def create(
        self,
        session: AsyncSession,
        user: User,
        message: Message,
        note: str,
    ) -> Ticket:
        existing = await session.scalar(
            select(Ticket).where(Ticket.source_message_id == message.id)
        )
        if existing:
            return existing
        since = datetime.now(UTC) - timedelta(days=1)
        count = await session.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.user_id == user.id, Ticket.created_at >= since)
        )
        if (count or 0) >= self.settings.ticket_daily_limit:
            raise HTTPException(429, "Günlük ticket limitine ulaşıldı.")
        category = message.category or "GENEL_DESTEK"
        ticket = Ticket(
            user_id=user.id,
            conversation_id=message.conversation_id,
            source_message_id=message.id,
            category=category,
            department=DEPARTMENTS.get(category, "Genel Destek"),
            user_note=note,
        )
        session.add(ticket)
        await session.flush()
        session.add(
            TicketStatusHistory(
                ticket_id=ticket.id,
                old_status=None,
                new_status="OPEN",
                note="Ticket kullanıcı olumsuz geri bildirimi sonrası oluşturuldu.",
            )
        )
        conversation = await session.get(Conversation, message.conversation_id)
        if conversation:
            conversation.status = "ESCALATED"
        await self.email.queue(
            session,
            user.email,
            f"Destek talebiniz alındı #{ticket.id}",
            (
                f"Destek talebiniz alınmıştır. Departman: {ticket.department}. "
                "En kısa sürede incelenecektir."
            ),
        )
        return ticket
