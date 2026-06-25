from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DemoProduct(Base):
    __tablename__ = "demo_products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str] = mapped_column(String(128), default="", index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    subcategory: Mapped[str] = mapped_column(String(64), default="", index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(8), default="TRY")
    stock: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    image_urls: Mapped[list[str]] = mapped_column(JSONB, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    returnable: Mapped[bool] = mapped_column(default=True)
    return_policy_note: Mapped[str] = mapped_column(Text, default="")
    warranty_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warranty_note: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    search_text: Mapped[str] = mapped_column(Text, default="")
    ai_context: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    reviews: Mapped[list["DemoProductReview"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    favorites: Mapped[list["DemoProductFavorite"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class DemoProductReview(Base):
    __tablename__ = "demo_product_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_demo_review_user_product"),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_demo_product_reviews_rating_0_5",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("demo_products.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    is_verified_purchase: Mapped[bool] = mapped_column(default=False)
    is_visible: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped["DemoProduct"] = relationship(back_populates="reviews")


class DemoProductFavorite(Base):
    __tablename__ = "demo_product_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_demo_favorite_user_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("demo_products.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product: Mapped["DemoProduct"] = relationship(back_populates="favorites")


class DemoReturnRequest(Base):
    __tablename__ = "demo_return_requests"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_demo_return_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("demo_orders.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    return_request: Mapped[str] = mapped_column(String(32), default="CREATED")
    return_code: Mapped[str] = mapped_column(String(64), default="", index=True)
    return_status: Mapped[str] = mapped_column(String(32), default="CREATED", index=True)
    refund_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    return_reason: Mapped[str] = mapped_column(Text, default="")
    return_tracking_no: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["DemoOrder"] = relationship(back_populates="return_request")
    refund: Mapped["DemoRefund | None"] = relationship(
        back_populates="return_request", uselist=False, cascade="all, delete-orphan"
    )


class DemoRefund(Base):
    __tablename__ = "demo_refunds"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    return_request_id: Mapped[int] = mapped_column(
        ForeignKey("demo_return_requests.id", ondelete="CASCADE"), unique=True, index=True
    )
    refund_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    refund_reference: Mapped[str] = mapped_column(String(128), default="")
    refund_reason: Mapped[str] = mapped_column(Text, default="")
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    return_request: Mapped["DemoReturnRequest"] = relationship(back_populates="refund")


class DemoWallet(Base):
    __tablename__ = "demo_wallets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="TRY")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    user: Mapped["User"] = relationship(back_populates="demo_wallet")


class DemoSavedCard(Base):
    __tablename__ = "demo_saved_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    card_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    card_brand: Mapped[str] = mapped_column(String(32), default="")
    last4: Mapped[str] = mapped_column(String(4), default="")
    holder_name: Mapped[str] = mapped_column(String(255), default="")
    is_default: Mapped[bool] = mapped_column(default=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    expiry_month: Mapped[int] = mapped_column(Integer, default=12)
    expiry_year: Mapped[int] = mapped_column(Integer, default=2030)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    user: Mapped["User"] = relationship(back_populates="saved_cards")


class DemoUserSecurityProfile(Base):
    __tablename__ = "demo_user_security_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    security_status: Mapped[str] = mapped_column(String(32), default="NORMAL", index=True)
    suspicious_login_count: Mapped[int] = mapped_column(Integer, default=0)
    email_verified_required: Mapped[bool] = mapped_column(default=False)
    phone_verified_required: Mapped[bool] = mapped_column(default=False)
    password_change_recommended: Mapped[bool] = mapped_column(default=False)
    risk_note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    user: Mapped["User"] = relationship(back_populates="security_profile")


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
    return_request: Mapped["DemoReturnRequest | None"] = relationship(
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


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, index=True
    )
    last_topic: Mapped[str] = mapped_column(String(64), default="")
    last_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("demo_products.id", ondelete="SET NULL"), nullable=True
    )
    last_product_name: Mapped[str] = mapped_column(String(255), default="")
    last_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("demo_orders.id", ondelete="SET NULL"), nullable=True
    )
    last_order_no: Mapped[str] = mapped_column(String(64), default="")
    last_return_id: Mapped[int | None] = mapped_column(
        ForeignKey("demo_return_requests.id", ondelete="SET NULL"), nullable=True
    )
    last_intent: Mapped[str] = mapped_column(String(64), default="")
    last_action: Mapped[str] = mapped_column(String(64), default="")
    last_mentioned_product_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    last_mentioned_order_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    state_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    conversation: Mapped["Conversation"] = relationship(back_populates="state")
