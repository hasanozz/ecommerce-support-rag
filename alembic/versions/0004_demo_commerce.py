"""Add demo commerce module.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rag_runs",
        sa.Column(
            "customer_context",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )

    op.create_table(
        "demo_products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("image_url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("name", "category", "is_active"):
        op.create_index(f"ix_demo_products_{column}", "demo_products", [column])

    op.create_table(
        "demo_coupons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="VALID"),
        sa.Column("discount_type", sa.String(16), nullable=False, server_default="PERCENT"),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("min_cart_total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("allowed_category", sa.String(64), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("code", "status", "is_active"):
        op.create_index(f"ix_demo_coupons_{column}", "demo_coupons", [column], unique=(column == "code"))

    op.create_table(
        "demo_carts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("coupon_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("user_id", "status"):
        op.create_index(f"ix_demo_carts_{column}", "demo_carts", [column])

    op.create_table(
        "demo_cart_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cart_id", sa.Integer(), sa.ForeignKey("demo_carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("demo_products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.UniqueConstraint("cart_id", "product_id", name="uq_demo_cart_item_product"),
    )
    for column in ("cart_id", "product_id"):
        op.create_index(f"ix_demo_cart_items_{column}", "demo_cart_items", [column])

    op.create_table(
        "demo_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_no", sa.String(64), nullable=False, unique=True),
        sa.Column("order_status", sa.String(32), nullable=False, server_default="CREATED"),
        sa.Column("payment_status", sa.String(32), nullable=False, server_default="SUCCESS"),
        sa.Column("shipping_status", sa.String(32), nullable=False, server_default="PREPARING"),
        sa.Column("coupon_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("admin_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("user_id", "order_no", "order_status", "payment_status", "shipping_status"):
        op.create_index(f"ix_demo_orders_{column}", "demo_orders", [column], unique=(column == "order_no"))

    op.create_table(
        "demo_order_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("demo_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("demo_products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
    )
    for column in ("order_id", "category"):
        op.create_index(f"ix_demo_order_items_{column}", "demo_order_items", [column])

    op.create_table(
        "demo_payment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("demo_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("provider_reference", sa.String(128), nullable=False, server_default=""),
        sa.Column("failure_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("user_id", "order_id", "status"):
        op.create_index(f"ix_demo_payment_attempts_{column}", "demo_payment_attempts", [column])

    op.create_table(
        "demo_shipments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("demo_orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("carrier", sa.String(100), nullable=False, server_default="Demo Kargo"),
        sa.Column("tracking_number", sa.String(100), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="PREPARING"),
        sa.Column("estimated_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delay_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("admin_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("order_id", "status"):
        op.create_index(f"ix_demo_shipments_{column}", "demo_shipments", [column], unique=(column == "order_id"))


def downgrade() -> None:
    op.drop_table("demo_shipments")
    op.drop_table("demo_payment_attempts")
    op.drop_table("demo_order_items")
    op.drop_table("demo_orders")
    op.drop_table("demo_cart_items")
    op.drop_table("demo_carts")
    op.drop_table("demo_coupons")
    op.drop_table("demo_products")
    op.drop_column("rag_runs", "customer_context")
