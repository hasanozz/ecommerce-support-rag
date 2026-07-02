from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from .context_resolver import ContextResolverOutput
from .data_resolver import DataResolverOutput, ResolvedDataEntities


class EvidencePurpose(str, Enum):
    PRODUCT_PROFILE = "PRODUCT_PROFILE"
    PRODUCT_CAPACITY = "PRODUCT_CAPACITY"
    PRODUCT_PRICE = "PRODUCT_PRICE"
    PRODUCT_STOCK = "PRODUCT_STOCK"
    PRODUCT_REVIEWS = "PRODUCT_REVIEWS"
    PRODUCT_RETURN_ELIGIBILITY = "PRODUCT_RETURN_ELIGIBILITY"
    ORDER_STATUS = "ORDER_STATUS"
    ORDER_CANCEL_ELIGIBILITY = "ORDER_CANCEL_ELIGIBILITY"
    ORDER_SHIPPING_STATUS = "ORDER_SHIPPING_STATUS"
    PAYMENT_STATUS = "PAYMENT_STATUS"
    PAYMENT_WITHOUT_ORDER = "PAYMENT_WITHOUT_ORDER"
    COUPON_STATUS = "COUPON_STATUS"
    COUPON_ELIGIBILITY = "COUPON_ELIGIBILITY"
    CART_STATUS = "CART_STATUS"
    RETURN_STATUS = "RETURN_STATUS"


class EvidenceEntityType(str, Enum):
    PRODUCT = "PRODUCT"
    ORDER = "ORDER"
    SHIPMENT = "SHIPMENT"
    PAYMENT = "PAYMENT"
    COUPON = "COUPON"
    CART = "CART"
    RETURN = "RETURN"
    REVIEW = "REVIEW"


class RequiredContext(BaseModel):
    source: str | None = None
    purpose: str
    entity_type: EvidenceEntityType | None = None
    required: bool = True
    fields_hint: list[str] = Field(default_factory=list)


class EvidenceFetcherInput(BaseModel):
    user_id: int = Field(ge=1)
    context_plan: ContextResolverOutput
    data_resolution: DataResolverOutput
    required_contexts: list[RequiredContext] = Field(default_factory=list)
    resolved_entities: ResolvedDataEntities | None = None

    @model_validator(mode="after")
    def validate_resolved_entities(self) -> "EvidenceFetcherInput":
        authoritative = self.data_resolution.resolved_entities
        if self.resolved_entities is None:
            self.resolved_entities = authoritative.model_copy(deep=True)
        elif self.resolved_entities != authoritative:
            raise ValueError(
                "resolved_entities must match data_resolution.resolved_entities"
            )
        return self


class EvidenceProvenance(BaseModel):
    source: str
    record_id: int


class EvidenceItem(BaseModel):
    source: str
    entity_type: EvidenceEntityType
    entity_id: int
    purpose: EvidencePurpose
    data: dict = Field(default_factory=dict)
    provenance: EvidenceProvenance


class MissingEvidence(BaseModel):
    source: str
    entity_type: EvidenceEntityType
    purpose: str
    reason: str


class EvidenceFetcherOutput(BaseModel):
    product_evidence: list[EvidenceItem] = Field(default_factory=list)
    order_evidence: list[EvidenceItem] = Field(default_factory=list)
    shipment_evidence: list[EvidenceItem] = Field(default_factory=list)
    payment_evidence: list[EvidenceItem] = Field(default_factory=list)
    coupon_evidence: list[EvidenceItem] = Field(default_factory=list)
    cart_evidence: list[EvidenceItem] = Field(default_factory=list)
    return_evidence: list[EvidenceItem] = Field(default_factory=list)
    review_evidence: list[EvidenceItem] = Field(default_factory=list)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

