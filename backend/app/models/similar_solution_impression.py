from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SimilarSolutionImpression(Base):
    __tablename__ = "similar_solution_impressions"
    __table_args__ = (
        UniqueConstraint(
            "similar_solution_id",
            "assistant_message_id",
            "user_id",
            name="uq_similar_solution_impression",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    similar_solution_id: Mapped[int] = mapped_column(
        ForeignKey("similar_solutions.id", ondelete="CASCADE"), index=True
    )
    assistant_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
