from __future__ import annotations

from datetime import datetime

from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class RagRun(Base):
    __tablename__ = "rag_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assistant_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True, index=True
    )
    rewritten_query: Mapped[str] = mapped_column(String(2000))
    retrieval_results: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    customer_context: Mapped[dict] = mapped_column(JSONB, default=dict)
    few_shot_examples: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    model_name: Mapped[str] = mapped_column(String(128), default="")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reranker_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    classifier_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_result: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    assistant_message: Mapped["Message"] = relationship(back_populates="rag_run")
