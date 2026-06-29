from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .context_resolver import ContextResolverOutput


class DataResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    SKIP = "SKIP"


class EntityType(str, Enum):
    PRODUCT = "PRODUCT"
    ORDER = "ORDER"
    COUPON = "COUPON"
    CART = "CART"
    PAYMENT = "PAYMENT"


class ReferenceType(str, Enum):
    ID = "ID"
    NAME = "NAME"
    ORDER_NO = "ORDER_NO"
    COUPON_CODE = "COUPON_CODE"
    LAST = "LAST"
    STATE_ID = "STATE_ID"
    FRONTEND_ID = "FRONTEND_ID"


class MatchType(str, Enum):
    EXACT_ID = "EXACT_ID"
    EXACT_NAME = "EXACT_NAME"
    EXACT_ORDER_NO = "EXACT_ORDER_NO"
    EXACT_COUPON_CODE = "EXACT_COUPON_CODE"
    FUZZY_NAME = "FUZZY_NAME"
    CONVERSATION_STATE = "CONVERSATION_STATE"
    FRONTEND_CONTEXT = "FRONTEND_CONTEXT"


class ResolutionNextStep(str, Enum):
    FETCH_EVIDENCE = "FETCH_EVIDENCE"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    FALLBACK = "FALLBACK"
    SKIP = "SKIP"


class EntityReference(BaseModel):
    entity_type: EntityType
    type: ReferenceType
    value: str | int


class DataResolverConversationState(BaseModel):
    last_product_id: int | None = Field(default=None, ge=1)
    last_order_id: int | None = Field(default=None, ge=1)
    last_cart_id: int | None = Field(default=None, ge=1)
    last_payment_id: int | None = Field(default=None, ge=1)
    last_intent: str | None = None
    last_action: str | None = None


class DataResolverFrontendContext(BaseModel):
    current_product_id: int | None = Field(default=None, ge=1)
    current_order_id: int | None = Field(default=None, ge=1)
    current_cart_id: int | None = Field(default=None, ge=1)
    current_payment_id: int | None = Field(default=None, ge=1)
    page_context: str | None = None


class DataResolverInput(BaseModel):
    request_id: str | None = None
    user_id: int = Field(ge=1)
    message: str = Field(min_length=1)
    context_plan: ContextResolverOutput
    entity_references: list[EntityReference] = Field(default_factory=list)
    conversation_state: DataResolverConversationState = Field(
        default_factory=DataResolverConversationState
    )
    frontend_context: DataResolverFrontendContext = Field(
        default_factory=DataResolverFrontendContext
    )


class ResolvedDataEntities(BaseModel):
    product_id: int | None = None
    order_id: int | None = None
    coupon_id: int | None = None
    cart_id: int | None = None
    payment_id: int | None = None


class MatchCandidate(BaseModel):
    record_id: int
    display_label: str
    confidence: float = Field(ge=0.0, le=1.0)
    match_type: MatchType


class EvidenceProvenance(BaseModel):
    source: str
    record_id: int


class EntityResolutionResult(BaseModel):
    entity_type: EntityType
    input_reference: EntityReference
    status: DataResolutionStatus
    resolved_id: int | None = None
    match_type: MatchType | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    candidates: list[MatchCandidate] = Field(default_factory=list)
    provenance: EvidenceProvenance | None = None


class EvidenceReference(BaseModel):
    entity_type: EntityType
    source: str
    record_id: int


class DataResolverOutput(BaseModel):
    status: DataResolutionStatus
    resolved_entities: ResolvedDataEntities = Field(default_factory=ResolvedDataEntities)
    entity_results: list[EntityResolutionResult] = Field(default_factory=list)
    missing_entities: list[EntityType] = Field(default_factory=list)
    ambiguous_entities: list[EntityType] = Field(default_factory=list)
    unfulfilled_contexts: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_step: ResolutionNextStep
