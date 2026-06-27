"""Add focused conversation state context fields.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_table("conversation_states"):
        return
    if not _has_column("conversation_states", "last_cart_id"):
        op.add_column(
            "conversation_states",
            sa.Column("last_cart_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_conversation_states_last_cart_id",
            "conversation_states",
            "demo_carts",
            ["last_cart_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _has_column("conversation_states", "last_payment_id"):
        op.add_column(
            "conversation_states",
            sa.Column("last_payment_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_conversation_states_last_payment_id",
            "conversation_states",
            "demo_payment_attempts",
            ["last_payment_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _has_column("conversation_states", "last_suggested_action"):
        op.add_column(
            "conversation_states",
            sa.Column("last_suggested_action", sa.String(length=64), nullable=False, server_default=""),
        )


def downgrade() -> None:
    if not _has_table("conversation_states"):
        return
    if _has_column("conversation_states", "last_suggested_action"):
        op.drop_column("conversation_states", "last_suggested_action")
    if _has_column("conversation_states", "last_payment_id"):
        op.drop_constraint(
            "fk_conversation_states_last_payment_id",
            "conversation_states",
            type_="foreignkey",
        )
        op.drop_column("conversation_states", "last_payment_id")
    if _has_column("conversation_states", "last_cart_id"):
        op.drop_constraint(
            "fk_conversation_states_last_cart_id",
            "conversation_states",
            type_="foreignkey",
        )
        op.drop_column("conversation_states", "last_cart_id")
