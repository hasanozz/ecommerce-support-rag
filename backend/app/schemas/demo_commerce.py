from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


ShippingStatus = Literal[
    "PREPARING",
    "SHIPPED",
    "IN_TRANSIT",
    "DELAYED",
    "LOST",
    "DELIVERED",
    "PARTIALLY_DELIVERED",
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
    sku: str
    name: str
    brand: str
    category: str
    subcategory: str
    price: Decimal
    currency: str
    stock: int
    is_active: bool
    image_url: str
    image_urls: list[str] = []
    description: str = ""
    returnable: bool = True
    warranty_months: int | None = None
    tags: list[str] = []
    rating_average: Decimal | None = None
    review_count: int = 0
    favorite_count: int = 0
    is_favorited: bool = False


class DemoProductReviewResponse(BaseModel):
    id: int
    product_id: int
    user_id: int
    user_display_name: str
    rating: int | None
    title: str
    body: str
    is_verified_purchase: bool
    is_visible: bool
    is_own_review: bool = False
    created_at: datetime
    updated_at: datetime


class DemoProductReviewUpsert(BaseModel):
    rating: int | None = Field(default=None, ge=0, le=5)
    title: str = Field(default="", max_length=255)
    body: str = Field(default="", max_length=2000)


class DemoProductDetailResponse(DemoProductResponse):
    attributes: dict = {}
    return_policy_note: str = ""
    warranty_note: str = ""
    reviews: list[DemoProductReviewResponse] = []


class DemoFavoriteResponse(BaseModel):
    id: int
    product: DemoProductResponse
    created_at: datetime


class AdminDemoProductResponse(DemoProductDetailResponse):
    search_text: str = ""
    ai_context: str = ""
    created_at: datetime
    updated_at: datetime


class AdminDemoReviewResponse(DemoProductReviewResponse):
    product_name: str
    user_email: str


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


class DemoRefundResponse(BaseModel):
    id: int
    refund_status: str
    refund_amount: Decimal
    refund_reference: str
    refund_reason: str
    initiated_at: datetime
    completed_at: datetime | None


class DemoReturnRequestResponse(BaseModel):
    id: int
    order_id: int
    order_no: str = ""
    user_id: int
    return_request: str
    return_code: str
    return_status: str
    refund_status: str
    return_reason: str
    return_tracking_no: str
    refund: DemoRefundResponse | None = None
    created_at: datetime
    updated_at: datetime


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
    return_request: DemoReturnRequestResponse | None = None


class DemoResetResponse(BaseModel):
    status: str
    products: int
    coupons: int
    orders: int


class DemoWalletResponse(BaseModel):
    id: int
    user_id: int
    balance: Decimal
    currency: str
    status: str
    updated_at: datetime


class DemoSavedCardResponse(BaseModel):
    id: int
    user_id: int
    card_token: str
    card_brand: str
    last4: str
    holder_name: str
    is_default: bool
    is_active: bool
    expiry_month: int
    expiry_year: int
    created_at: datetime


class DemoSecurityProfileResponse(BaseModel):
    id: int
    user_id: int
    security_status: str
    suspicious_login_count: int
    email_verified_required: bool
    phone_verified_required: bool
    password_change_recommended: bool
    risk_note: str
    updated_at: datetime


class AdminOrderUpdate(BaseModel):
    order_status: OrderStatus | None = None
    payment_status: PaymentStatus | None = None
    admin_note: str = Field(default="", max_length=1000)


class AdminReturnRequestUpdate(BaseModel):
    return_request: str | None = Field(default=None, max_length=32)
    return_status: str | None = Field(default=None, max_length=32)
    refund_status: str | None = Field(default=None, max_length=32)
    return_reason: str | None = Field(default=None, max_length=2000)
    return_tracking_no: str | None = Field(default=None, max_length=100)
    return_code: str | None = Field(default=None, max_length=64)
    refund_reference: str | None = Field(default=None, max_length=128)
    refund_amount: Decimal | None = Field(default=None, ge=0)
    refund_reason: str | None = Field(default=None, max_length=2000)


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
