from __future__ import annotations

import asyncio
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..models import EmailOutbox


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def queue(
        self, session: AsyncSession, recipient: str, subject: str, body: str
    ) -> EmailOutbox:
        item = EmailOutbox(recipient=recipient, subject=subject, body=body)
        session.add(item)
        await session.flush()
        return item

    def _send_sync(self, item: EmailOutbox) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from_email
        message["To"] = item.recipient
        message["Subject"] = item.subject
        message.set_content(item.body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(
                    self.settings.smtp_username, self.settings.smtp_password
                )
            smtp.send_message(message)

    async def send_pending(self, session: AsyncSession, limit: int = 20) -> int:
        if not self.settings.smtp_from_email:
            return 0
        items = (
            await session.scalars(
                select(EmailOutbox)
                .where(EmailOutbox.status.in_(["PENDING", "FAILED"]))
                .order_by(EmailOutbox.id)
                .limit(limit)
            )
        ).all()
        sent = 0
        for item in items:
            try:
                await asyncio.to_thread(self._send_sync, item)
                item.status = "SENT"
                item.sent_at = datetime.now(UTC)
                item.last_error = ""
                sent += 1
            except Exception as exc:  # SMTP failures must not break ticket creation.
                item.status = "FAILED"
                item.attempt_count += 1
                item.last_error = str(exc)[:1000]
        await session.commit()
        return sent


async def process_outbox_once() -> None:
    from ..database import SessionLocal

    async with SessionLocal() as session:
        await EmailService().send_pending(session)
