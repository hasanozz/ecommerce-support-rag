"""Create RAG core tables.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "documents",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("subcategory", sa.String(160), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_documents_category", "documents", ["category"])
    op.create_index("ix_documents_subcategory", "documents", ["subcategory"], unique=True)
    op.create_index("ix_documents_title", "documents", ["title"])
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(180), primary_key=True),
        sa.Column(
            "doc_id",
            sa.String(128),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("subcategory", sa.String(160), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("section", sa.String(80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contextual_content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
    )
    for column in ("doc_id", "category", "subcategory", "section"):
        op.create_index(f"ix_chunks_{column}", "chunks", [column])
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "query_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("retrieved_chunks", postgresql.JSONB(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("query_logs")
    op.drop_table("chunks")
    op.drop_table("documents")
