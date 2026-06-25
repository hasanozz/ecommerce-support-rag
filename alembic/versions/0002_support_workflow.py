"""Create user, conversation, feedback and ticket workflow.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.String(1000), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_admin", "users", ["is_admin"])
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("user_id", "token_hash", "ip_hash", "expires_at"):
        op.create_index(f"ix_user_sessions_{column}", "user_sessions", [column])
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(255), nullable=False, server_default="Yeni görüşme"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE")),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("safe_content", sa.Text(), nullable=False),
        sa.Column("canonical_query", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("sources", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("security_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unhelpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("conversation_id", "role", "canonical_query", "category", "ip_hash"):
        op.create_index(f"ix_messages_{column}", "messages", [column])
    op.create_table(
        "rag_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), unique=True),
        sa.Column("rewritten_query", sa.String(2000), nullable=False),
        sa.Column("retrieval_results", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("few_shot_examples", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rag_runs_assistant_message_id", "rag_runs", ["assistant_message_id"], unique=True)
    op.create_table(
        "similar_solutions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("canonical_question", sa.Text(), nullable=False),
        sa.Column("safe_answer", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unhelpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_similar_solutions_category", "similar_solutions", ["category"])
    op.create_index("ix_similar_solutions_is_published", "similar_solutions", ["is_published"])
    op.create_index(
        "ix_similar_solutions_embedding_hnsw",
        "similar_solutions",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("similar_solution_id", sa.Integer(), sa.ForeignKey("similar_solutions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("value", sa.String(16), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("(message_id IS NOT NULL) <> (similar_solution_id IS NOT NULL)", name="ck_feedback_single_target"),
        sa.UniqueConstraint("user_id", "message_id", name="uq_feedback_user_message"),
        sa.UniqueConstraint("user_id", "similar_solution_id", name="uq_feedback_user_similar"),
    )
    for column in ("user_id", "message_id", "similar_solution_id", "ip_hash"):
        op.create_index(f"ix_feedback_{column}", "feedback", [column])
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE")),
        sa.Column("source_message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="RESTRICT"), unique=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("user_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("admin_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("user_id", "conversation_id", "source_message_id", "category", "department", "status"):
        op.create_index(f"ix_tickets_{column}", "tickets", [column])
    op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("tickets.id", ondelete="CASCADE")),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("old_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ticket_status_history_ticket_id", "ticket_status_history", ["ticket_id"])
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_outbox_recipient", "email_outbox", ["recipient"])
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])


def downgrade() -> None:
    for table in [
        "email_outbox",
        "ticket_status_history",
        "tickets",
        "feedback",
        "similar_solutions",
        "rag_runs",
        "messages",
        "conversations",
        "user_sessions",
        "users",
    ]:
        op.drop_table(table)
