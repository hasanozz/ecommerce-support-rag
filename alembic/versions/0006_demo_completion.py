"""Expand demo completion scenario layer.

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_index(table: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table))


def upgrade() -> None:
    if not _has_table("demo_return_requests"):
        op.create_table(
            "demo_return_requests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "order_id",
                sa.Integer(),
                sa.ForeignKey("demo_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("return_request", sa.String(32), nullable=False, server_default="CREATED"),
            sa.Column("return_code", sa.String(64), nullable=False, server_default=""),
            sa.Column("return_status", sa.String(32), nullable=False, server_default="CREATED"),
            sa.Column("refund_status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("return_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("return_tracking_no", sa.String(100), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("order_id", name="uq_demo_return_order"),
        )
    if _has_table("demo_return_requests"):
        for index_name, columns, unique in [
            ("ix_demo_return_requests_order_id", ["order_id"], False),
            ("ix_demo_return_requests_user_id", ["user_id"], False),
            ("ix_demo_return_requests_return_code", ["return_code"], False),
            ("ix_demo_return_requests_return_status", ["return_status"], False),
            ("ix_demo_return_requests_refund_status", ["refund_status"], False),
        ]:
            if not _has_index("demo_return_requests", index_name):
                op.create_index(index_name, "demo_return_requests", columns, unique=unique)

    if not _has_table("demo_refunds"):
        op.create_table(
            "demo_refunds",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "return_request_id",
                sa.Integer(),
                sa.ForeignKey("demo_return_requests.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("refund_status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("refund_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("refund_reference", sa.String(128), nullable=False, server_default=""),
            sa.Column("refund_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("initiated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("return_request_id", name="uq_demo_refunds_return_request"),
        )
    if _has_table("demo_refunds"):
        if not _has_index("demo_refunds", "ix_demo_refunds_return_request_id"):
            op.create_index("ix_demo_refunds_return_request_id", "demo_refunds", ["return_request_id"])
        if not _has_index("demo_refunds", "ix_demo_refunds_refund_status"):
            op.create_index("ix_demo_refunds_refund_status", "demo_refunds", ["refund_status"])

    if not _has_table("demo_wallets"):
        op.create_table(
            "demo_wallets",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("balance", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(8), nullable=False, server_default="TRY"),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", name="uq_demo_wallet_user"),
        )
    if _has_table("demo_wallets"):
        if not _has_index("demo_wallets", "ix_demo_wallets_user_id"):
            op.create_index("ix_demo_wallets_user_id", "demo_wallets", ["user_id"])
        if not _has_index("demo_wallets", "ix_demo_wallets_status"):
            op.create_index("ix_demo_wallets_status", "demo_wallets", ["status"])

    if not _has_table("demo_saved_cards"):
        op.create_table(
            "demo_saved_cards",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("card_token", sa.String(128), nullable=False),
            sa.Column("card_brand", sa.String(32), nullable=False, server_default=""),
            sa.Column("last4", sa.String(4), nullable=False, server_default=""),
            sa.Column("holder_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("expiry_month", sa.Integer(), nullable=False, server_default="12"),
            sa.Column("expiry_year", sa.Integer(), nullable=False, server_default="2030"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("card_token", name="uq_demo_saved_cards_token"),
        )
    if _has_table("demo_saved_cards"):
        for index_name, columns, unique in [
            ("ix_demo_saved_cards_user_id", ["user_id"], False),
            ("ix_demo_saved_cards_card_token", ["card_token"], False),
            ("ix_demo_saved_cards_is_default", ["is_default"], False),
            ("ix_demo_saved_cards_is_active", ["is_active"], False),
        ]:
            if not _has_index("demo_saved_cards", index_name):
                op.create_index(index_name, "demo_saved_cards", columns, unique=unique)

    if not _has_table("demo_user_security_profiles"):
        op.create_table(
            "demo_user_security_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("security_status", sa.String(32), nullable=False, server_default="NORMAL"),
            sa.Column(
                "suspicious_login_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "email_verified_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "phone_verified_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "password_change_recommended",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("risk_note", sa.Text(), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", name="uq_demo_security_profile_user"),
        )
    if _has_table("demo_user_security_profiles"):
        if not _has_index("demo_user_security_profiles", "ix_demo_user_security_profiles_user_id"):
            op.create_index(
                "ix_demo_user_security_profiles_user_id",
                "demo_user_security_profiles",
                ["user_id"],
            )
        if not _has_index("demo_user_security_profiles", "ix_demo_user_security_profiles_security_status"):
            op.create_index(
                "ix_demo_user_security_profiles_security_status",
                "demo_user_security_profiles",
                ["security_status"],
            )

    if not _has_table("conversation_states"):
        op.create_table(
            "conversation_states",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "conversation_id",
                sa.Integer(),
                sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("last_topic", sa.String(64), nullable=False, server_default=""),
            sa.Column(
                "last_product_id",
                sa.Integer(),
                sa.ForeignKey("demo_products.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("last_product_name", sa.String(255), nullable=False, server_default=""),
            sa.Column(
                "last_order_id",
                sa.Integer(),
                sa.ForeignKey("demo_orders.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("last_order_no", sa.String(64), nullable=False, server_default=""),
            sa.Column(
                "last_return_id",
                sa.Integer(),
                sa.ForeignKey("demo_return_requests.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("last_intent", sa.String(64), nullable=False, server_default=""),
            sa.Column("last_action", sa.String(64), nullable=False, server_default=""),
            sa.Column(
                "last_mentioned_product_ids",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "last_mentioned_order_ids",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "state_metadata",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("conversation_id", name="uq_conversation_states_conversation"),
        )
    if _has_table("conversation_states"):
        if not _has_index("conversation_states", "ix_conversation_states_conversation_id"):
            op.create_index(
                "ix_conversation_states_conversation_id",
                "conversation_states",
                ["conversation_id"],
            )


def downgrade() -> None:
    op.drop_index("ix_conversation_states_conversation_id", table_name="conversation_states")
    op.drop_table("conversation_states")

    op.drop_index(
        "ix_demo_user_security_profiles_security_status",
        table_name="demo_user_security_profiles",
    )
    op.drop_index(
        "ix_demo_user_security_profiles_user_id",
        table_name="demo_user_security_profiles",
    )
    op.drop_table("demo_user_security_profiles")

    op.drop_index("ix_demo_saved_cards_is_active", table_name="demo_saved_cards")
    op.drop_index("ix_demo_saved_cards_is_default", table_name="demo_saved_cards")
    op.drop_index("ix_demo_saved_cards_card_token", table_name="demo_saved_cards")
    op.drop_index("ix_demo_saved_cards_user_id", table_name="demo_saved_cards")
    op.drop_table("demo_saved_cards")

    op.drop_index("ix_demo_wallets_status", table_name="demo_wallets")
    op.drop_index("ix_demo_wallets_user_id", table_name="demo_wallets")
    op.drop_table("demo_wallets")

    op.drop_index("ix_demo_refunds_refund_status", table_name="demo_refunds")
    op.drop_index("ix_demo_refunds_return_request_id", table_name="demo_refunds")
    op.drop_table("demo_refunds")

    op.drop_index("ix_demo_return_requests_refund_status", table_name="demo_return_requests")
    op.drop_index("ix_demo_return_requests_return_status", table_name="demo_return_requests")
    op.drop_index("ix_demo_return_requests_return_code", table_name="demo_return_requests")
    op.drop_index("ix_demo_return_requests_user_id", table_name="demo_return_requests")
    op.drop_index("ix_demo_return_requests_order_id", table_name="demo_return_requests")
    op.drop_table("demo_return_requests")
