from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), index=True)
    safe_content: Mapped[str] = mapped_column(Text)
    canonical_query: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    security_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    unhelpful_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    rag_run: Mapped["RagRun | None"] = relationship(
        back_populates="assistant_message", uselist=False, cascade="all, delete-orphan"
    )
