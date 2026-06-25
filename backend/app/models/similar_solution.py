from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..config import get_settings
from .base import Base


class SimilarSolution(Base):
    __tablename__ = "similar_solutions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_question: Mapped[str] = mapped_column(Text)
    safe_answer: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(get_settings().embedding_dimension)
    )
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    unhelpful_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


Index(
    "ix_similar_solutions_embedding_hnsw",
    SimilarSolution.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
