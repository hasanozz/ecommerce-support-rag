from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ContextIntent(str, Enum):
    PRODUCT_ATTRIBUTE = "PRODUCT_ATTRIBUTE"
    PRODUCT_STOCK = "PRODUCT_STOCK"
    PRODUCT_PRICE = "PRODUCT_PRICE"
    PRODUCT_REVIEWS = "PRODUCT_REVIEWS"
    PRODUCT_RETURN_ELIGIBILITY = "PRODUCT_RETURN_ELIGIBILITY"
    ORDER_STATUS = "ORDER_STATUS"
    ORDER_CANCEL = "ORDER_CANCEL"
    ORDER_SHIPPING_DELAY = "ORDER_SHIPPING_DELAY"
    DELIVERED_NOT_RECEIVED = "DELIVERED_NOT_RECEIVED"
    RETURN_CREATE = "RETURN_CREATE"
    PAYMENT_CHARGED_ORDER_NOT_CREATED = "PAYMENT_CHARGED_ORDER_NOT_CREATED"
    COUPON_INVALID = "COUPON_INVALID"
    COUPON_EXPIRED = "COUPON_EXPIRED"
    CAMPAIGN_USAGE = "CAMPAIGN_USAGE"
    SUPPORT_POLICY_ONLY = "SUPPORT_POLICY_ONLY"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    UNCLEAR = "UNCLEAR"
    UNSAFE = "UNSAFE"


class ClassifierEntities(BaseModel):
    product_id: int | None = Field(default=None, ge=1)
    product_name: str | None = None
    order_id: int | None = Field(default=None, ge=1)
    order_no: str | None = None
    coupon_code: str | None = None
    category: str | None = None


class ClassifierOutput(BaseModel):
    domain: str | None = None
    intent: str
    category: str | None = None
    subcategory: str | None = None
    doc_id: str | None = None
    entities: ClassifierEntities = Field(default_factory=ClassifierEntities)
    requested_info: str | None = None
    requested_information: list[str] = Field(default_factory=list)
    expected_action: str | None = None
    priority: str | None = None
    routing_hints: dict = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ResolverConversationState(BaseModel):
    last_product_id: int | None = Field(default=None, ge=1)
    last_order_id: int | None = Field(default=None, ge=1)
    last_intent: str | None = None
    last_action: str | None = None


class ContextResolverInput(BaseModel):
    message: str = Field(min_length=1)
    classifier_output: ClassifierOutput
    conversation_state: ResolverConversationState = Field(
        default_factory=ResolverConversationState
    )


class ResolvedEntities(BaseModel):
    product_id: int | None = None
    product_name: str | None = None
    order_id: int | None = None
    order_no: str | None = None
    coupon_code: str | None = None
    category: str | None = None


class ContextResolverOutput(BaseModel):
    resolved_entities: ResolvedEntities
    data_sources: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    needs_support_rag: bool = False
    support_doc_ids: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_reason: str | None = None
    fallback_reason: str | None = None
    next_step: Literal["FETCH_CONTEXT", "CLARIFY", "FALLBACK"]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
