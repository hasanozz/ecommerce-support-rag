"""Expand demo product catalog.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    return any(col["name"] == column for col in _inspector().get_columns(table))


def _has_index(table: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table))


def upgrade() -> None:
    product_columns = [
        sa.Column("sku", sa.String(64), nullable=True),
        sa.Column("brand", sa.String(128), nullable=False, server_default=""),
        sa.Column("subcategory", sa.String(64), nullable=False, server_default=""),
        sa.Column("currency", sa.String(8), nullable=False, server_default="TRY"),
        sa.Column(
            "image_urls",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("returnable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("return_policy_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("warranty_months", sa.Integer(), nullable=True),
        sa.Column("warranty_note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "attributes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("ai_context", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]

    for column in product_columns:
        if not _has_column("demo_products", column.name):
            op.add_column("demo_products", column)

    if _has_column("demo_products", "sku"):
        op.execute("UPDATE demo_products SET sku = 'DEMO-PRODUCT-' || id WHERE sku IS NULL")
        op.alter_column("demo_products", "sku", existing_type=sa.String(64), nullable=False)

    if not _has_index("demo_products", "ix_demo_products_sku"):
        op.create_index("ix_demo_products_sku", "demo_products", ["sku"], unique=True)
    if not _has_index("demo_products", "ix_demo_products_brand"):
        op.create_index("ix_demo_products_brand", "demo_products", ["brand"])
    if not _has_index("demo_products", "ix_demo_products_subcategory"):
        op.create_index("ix_demo_products_subcategory", "demo_products", ["subcategory"])

    if not _has_table("demo_product_reviews"):
        op.create_table(
            "demo_product_reviews",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "product_id",
                sa.Integer(),
                sa.ForeignKey("demo_products.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "is_verified_purchase",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "product_id", name="uq_demo_review_user_product"),
            sa.CheckConstraint(
                "rating IS NULL OR (rating >= 0 AND rating <= 5)",
                name="ck_demo_product_reviews_rating_0_5",
            ),
        )
    if _has_table("demo_product_reviews"):
        if not _has_index("demo_product_reviews", "ix_demo_product_reviews_product_id"):
            op.create_index(
                "ix_demo_product_reviews_product_id", "demo_product_reviews", ["product_id"]
            )
        if not _has_index("demo_product_reviews", "ix_demo_product_reviews_user_id"):
            op.create_index(
                "ix_demo_product_reviews_user_id", "demo_product_reviews", ["user_id"]
            )
        if not _has_index("demo_product_reviews", "ix_demo_product_reviews_is_visible"):
            op.create_index(
                "ix_demo_product_reviews_is_visible", "demo_product_reviews", ["is_visible"]
            )

    if not _has_table("demo_product_favorites"):
        op.create_table(
            "demo_product_favorites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "product_id",
                sa.Integer(),
                sa.ForeignKey("demo_products.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "user_id", "product_id", name="uq_demo_favorite_user_product"
            ),
        )
    if _has_table("demo_product_favorites"):
        if not _has_index("demo_product_favorites", "ix_demo_product_favorites_user_id"):
            op.create_index(
                "ix_demo_product_favorites_user_id", "demo_product_favorites", ["user_id"]
            )
        if not _has_index("demo_product_favorites", "ix_demo_product_favorites_product_id"):
            op.create_index(
                "ix_demo_product_favorites_product_id",
                "demo_product_favorites",
                ["product_id"],
            )


def downgrade() -> None:
    op.drop_table("demo_product_favorites")
    op.drop_table("demo_product_reviews")
    op.drop_index("ix_demo_products_subcategory", table_name="demo_products")
    op.drop_index("ix_demo_products_brand", table_name="demo_products")
    op.drop_index("ix_demo_products_sku", table_name="demo_products")
    op.drop_column("demo_products", "updated_at")
    op.drop_column("demo_products", "ai_context")
    op.drop_column("demo_products", "search_text")
    op.drop_column("demo_products", "attributes")
    op.drop_column("demo_products", "tags")
    op.drop_column("demo_products", "warranty_note")
    op.drop_column("demo_products", "warranty_months")
    op.drop_column("demo_products", "return_policy_note")
    op.drop_column("demo_products", "returnable")
    op.drop_column("demo_products", "description")
    op.drop_column("demo_products", "image_urls")
    op.drop_column("demo_products", "currency")
    op.drop_column("demo_products", "subcategory")
    op.drop_column("demo_products", "brand")
    op.drop_column("demo_products", "sku")
