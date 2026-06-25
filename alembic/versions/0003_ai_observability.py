"""Add AI observability and embedding metadata.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_runs", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column(
        "rag_runs", sa.Column("completion_tokens", sa.Integer(), nullable=True)
    )
    op.add_column("rag_runs", sa.Column("total_tokens", sa.Integer(), nullable=True))
    op.add_column(
        "rag_runs", sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True)
    )
    op.add_column("rag_runs", sa.Column("retrieval_score", sa.Float(), nullable=True))
    op.add_column("rag_runs", sa.Column("reranker_score", sa.Float(), nullable=True))
    op.add_column(
        "rag_runs", sa.Column("classifier_confidence", sa.Float(), nullable=True)
    )
    op.add_column(
        "rag_runs", sa.Column("composite_confidence", sa.Float(), nullable=True)
    )
    op.add_column(
        "rag_runs",
        sa.Column(
            "classification_result",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )

    op.create_table(
        "embedding_ingests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("dataset_checksum", sa.String(64), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("ingest_version", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_embedding_ingests_is_active", "embedding_ingests", ["is_active"]
    )

    op.create_table(
        "similar_solution_impressions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "similar_solution_id",
            sa.Integer(),
            sa.ForeignKey("similar_solutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assistant_message_id",
            sa.Integer(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "similar_solution_id",
            "assistant_message_id",
            "user_id",
            name="uq_similar_solution_impression",
        ),
    )
    for column in ("similar_solution_id", "assistant_message_id", "user_id"):
        op.create_index(
            f"ix_similar_solution_impressions_{column}",
            "similar_solution_impressions",
            [column],
        )


def downgrade() -> None:
    op.drop_table("similar_solution_impressions")
    op.drop_table("embedding_ingests")
    for column in (
        "classification_result",
        "composite_confidence",
        "classifier_confidence",
        "reranker_score",
        "retrieval_score",
        "estimated_cost",
        "total_tokens",
        "completion_tokens",
        "prompt_tokens",
    ):
        op.drop_column("rag_runs", column)
