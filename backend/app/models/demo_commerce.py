from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DemoProduct(Base):
    __tablename__ = "demo_products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DemoCart(Base):
    __tablename__ = "demo_carts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    coupon_code: Mapped[str] = mapped_column(String(64), default="")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["DemoCartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class DemoCartItem(Base):
    __tablename__ = "demo_cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_demo_cart_item_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(
        ForeignKey("demo_carts.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("demo_products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    cart: Mapped["DemoCart"] = relationship(back_populates="items")
    product: Mapped["DemoProduct"] = relationship()


class DemoCoupon(Base):
    __tablename__ = "demo_coupons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="VALID", index=True)
    discount_type: Mapped[str] = mapped_column(String(16), default="PERCENT")
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    min_cart_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    allowed_category: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DemoOrder(Base):
    __tablename__ = "demo_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_status: Mapped[str] = mapped_column(String(32), default="CREATED", index=True)
    payment_status: Mapped[str] = mapped_column(String(32), default="SUCCESS", index=True)
    shipping_status: Mapped[str] = mapped_column(String(32), default="PREPARING", index=True)
    coupon_code: Mapped[str] = mapped_column(String(64), default="")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    admin_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["DemoOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    shipment: Mapped["DemoShipment | None"] = relationship(
        back_populates="order", uselist=False, cascade="all, delete-orphan"
    )


class DemoOrderItem(Base):
    __tablename__ = "demo_order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("demo_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("demo_products.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[int] = mapped_column(default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped["DemoOrder"] = relationship(back_populates="items")


class DemoPaymentAttempt(Base):
    __tablename__ = "demo_payment_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("demo_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    provider_reference: Mapped[str] = mapped_column(String(128), default="")
    failure_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DemoShipment(Base):
    __tablename__ = "demo_shipments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("demo_orders.id", ondelete="CASCADE"), unique=True, index=True
    )
    carrier: Mapped[str] = mapped_column(String(100), default="Demo Kargo")
    tracking_number: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(32), default="PREPARING", index=True)
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delay_reason: Mapped[str] = mapped_column(String(255), default="")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["DemoOrder"] = relationship(back_populates="shipment")
