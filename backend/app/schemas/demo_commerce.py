from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


ShippingStatus = Literal[
    "PREPARING", "SHIPPED", "IN_TRANSIT", "DELAYED", "LOST", "DELIVERED"
]
PaymentStatus = Literal["SUCCESS", "FAILED", "CAPTURED_NO_ORDER", "REFUND_PENDING"]
CouponStatus = Literal[
    "VALID", "EXPIRED", "MIN_CART_NOT_MET", "CATEGORY_MISMATCH", "USED", "DISABLED"
]
OrderStatus = Literal[
    "CREATED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED", "REFUND_PENDING"
]


class DemoProductResponse(BaseModel):
    id: int
    name: str
    category: str
    price: Decimal
    stock: int
    is_active: bool
    image_url: str


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=20)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=20)


class CouponApplyRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class DemoCartItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    category: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class DemoCartResponse(BaseModel):
    id: int
    status: str
    coupon_code: str
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    items: list[DemoCartItemResponse]
    coupon_message: str = ""


class DemoOrderItemResponse(BaseModel):
    product_name: str
    category: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class DemoShipmentResponse(BaseModel):
    carrier: str
    tracking_number: str
    status: str
    estimated_delivery_at: datetime | None
    delivered_at: datetime | None
    delay_reason: str
    admin_note: str


class DemoOrderResponse(BaseModel):
    id: int
    order_no: str
    order_status: str
    payment_status: str
    shipping_status: str
    coupon_code: str
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    admin_note: str
    created_at: datetime
    updated_at: datetime
    items: list[DemoOrderItemResponse] = []
    shipment: DemoShipmentResponse | None = None


class DemoResetResponse(BaseModel):
    status: str
    products: int
    coupons: int
    orders: int


class AdminOrderUpdate(BaseModel):
    order_status: OrderStatus | None = None
    payment_status: PaymentStatus | None = None
    admin_note: str = Field(default="", max_length=1000)


class AdminShipmentUpdate(BaseModel):
    shipping_status: ShippingStatus
    carrier: str = Field(default="Demo Kargo", max_length=100)
    tracking_number: str = Field(default="", max_length=100)
    delay_reason: str = Field(default="", max_length=255)
    admin_note: str = Field(default="", max_length=1000)
    estimated_delivery_at: datetime | None = None
    delivered_at: datetime | None = None


class AdminCouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    status: CouponStatus = "VALID"
    discount_type: Literal["PERCENT", "AMOUNT"] = "PERCENT"
    discount_value: Decimal = Field(default=10, ge=0)
    min_cart_total: Decimal = Field(default=0, ge=0)
    allowed_category: str = Field(default="", max_length=64)
    expires_at: datetime | None = None
    is_active: bool = True


class AdminCouponUpdate(AdminCouponCreate):
    pass


class DemoCouponResponse(BaseModel):
    id: int
    code: str
    status: str
    discount_type: str
    discount_value: Decimal
    min_cart_total: Decimal
    allowed_category: str
    expires_at: datetime | None
    is_active: bool


class AdminPaymentAttemptCreate(BaseModel):
    user_id: int
    order_id: int | None = None
    status: PaymentStatus
    amount: Decimal = Field(default=0, ge=0)
    provider_reference: str = Field(default="", max_length=128)
    failure_reason: str = Field(default="", max_length=255)
