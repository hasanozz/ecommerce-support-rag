from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "(message_id IS NOT NULL) <> (similar_solution_id IS NOT NULL)",
            name="ck_feedback_single_target",
        ),
        UniqueConstraint("user_id", "message_id", name="uq_feedback_user_message"),
        UniqueConstraint(
            "user_id", "similar_solution_id", name="uq_feedback_user_similar"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    similar_solution_id: Mapped[int | None] = mapped_column(
        ForeignKey("similar_solutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(16))
    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
