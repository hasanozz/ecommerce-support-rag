"""Add demo product aliases.

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_product_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalized_alias", sa.String(255), nullable=False),
        sa.Column("alias_type", sa.String(32), nullable=False),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("demo_products.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("category", sa.String(64), nullable=False, server_default=""),
        sa.Column("subcategory", sa.String(64), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("source", sa.String(64), nullable=False, server_default="demo_seed"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "normalized_alias",
            "alias_type",
            name="uq_demo_product_alias_scope",
        ),
    )
    op.create_index("ix_demo_product_aliases_alias", "demo_product_aliases", ["alias"])
    op.create_index(
        "ix_demo_product_aliases_normalized_alias",
        "demo_product_aliases",
        ["normalized_alias"],
    )
    op.create_index(
        "ix_demo_product_aliases_alias_type",
        "demo_product_aliases",
        ["alias_type"],
    )
    op.create_index(
        "ix_demo_product_aliases_product_id",
        "demo_product_aliases",
        ["product_id"],
    )
    op.create_index(
        "ix_demo_product_aliases_category",
        "demo_product_aliases",
        ["category"],
    )
    op.create_index(
        "ix_demo_product_aliases_subcategory",
        "demo_product_aliases",
        ["subcategory"],
    )
    op.create_index(
        "ix_demo_product_aliases_is_active",
        "demo_product_aliases",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_demo_product_aliases_is_active", table_name="demo_product_aliases")
    op.drop_index("ix_demo_product_aliases_subcategory", table_name="demo_product_aliases")
    op.drop_index("ix_demo_product_aliases_category", table_name="demo_product_aliases")
    op.drop_index("ix_demo_product_aliases_product_id", table_name="demo_product_aliases")
    op.drop_index("ix_demo_product_aliases_alias_type", table_name="demo_product_aliases")
    op.drop_index(
        "ix_demo_product_aliases_normalized_alias",
        table_name="demo_product_aliases",
    )
    op.drop_index("ix_demo_product_aliases_alias", table_name="demo_product_aliases")
    op.drop_table("demo_product_aliases")
