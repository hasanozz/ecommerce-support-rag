from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..schemas.evidence_fetcher import (
    EvidenceEntityType,
    EvidenceFetcherInput,
    EvidenceFetcherOutput,
    EvidenceItem,
    EvidenceProvenance,
    EvidencePurpose,
    MissingEvidence,
    RequiredContext,
)


@dataclass(frozen=True, slots=True)
class PurposeSpec:
    source: str
    entity_type: EvidenceEntityType
    resolved_id_field: str
    output_field: str
    allowed_fields: tuple[str, ...]


PURPOSE_SPECS: dict[EvidencePurpose, PurposeSpec] = {
    EvidencePurpose.PRODUCT_CAPACITY: PurposeSpec(
        "PRODUCT_CATALOG",
        EvidenceEntityType.PRODUCT,
        "product_id",
        "product_evidence",
        ("name", "capacity_ml", "volume_ml"),
    ),
    EvidencePurpose.PRODUCT_PRICE: PurposeSpec(
        "PRODUCT_CATALOG",
        EvidenceEntityType.PRODUCT,
        "product_id",
        "product_evidence",
        ("price", "discounted_price", "currency"),
    ),
    EvidencePurpose.PRODUCT_STOCK: PurposeSpec(
        "PRODUCT_CATALOG",
        EvidenceEntityType.PRODUCT,
        "product_id",
        "product_evidence",
        ("stock", "availability"),
    ),
    EvidencePurpose.PRODUCT_REVIEWS: PurposeSpec(
        "REVIEW_STORE",
        EvidenceEntityType.REVIEW,
        "product_id",
        "review_evidence",
        ("rating_average", "review_count", "reviews"),
    ),
    EvidencePurpose.PRODUCT_RETURN_ELIGIBILITY: PurposeSpec(
        "PRODUCT_CATALOG",
        EvidenceEntityType.PRODUCT,
        "product_id",
        "product_evidence",
        ("returnable", "return_policy_note", "category"),
    ),
    EvidencePurpose.ORDER_STATUS: PurposeSpec(
        "ORDER_LEDGER",
        EvidenceEntityType.ORDER,
        "order_id",
        "order_evidence",
        ("order_no", "order_status", "shipping_status", "payment_status"),
    ),
    EvidencePurpose.ORDER_CANCEL_ELIGIBILITY: PurposeSpec(
        "ORDER_LEDGER",
        EvidenceEntityType.ORDER,
        "order_id",
        "order_evidence",
        ("order_no", "order_status", "shipping_status", "cancel_eligibility"),
    ),
    EvidencePurpose.ORDER_SHIPPING_STATUS: PurposeSpec(
        "ORDER_LEDGER",
        EvidenceEntityType.ORDER,
        "order_id",
        "order_evidence",
        (
            "order_no",
            "shipping_status",
            "tracking_number",
            "estimated_delivery_at",
            "delay_reason",
        ),
    ),
    EvidencePurpose.PAYMENT_STATUS: PurposeSpec(
        "PAYMENT_LEDGER",
        EvidenceEntityType.PAYMENT,
        "payment_id",
        "payment_evidence",
        ("status", "amount", "provider_reference", "order_id"),
    ),
    EvidencePurpose.PAYMENT_WITHOUT_ORDER: PurposeSpec(
        "PAYMENT_LEDGER",
        EvidenceEntityType.PAYMENT,
        "payment_id",
        "payment_evidence",
        ("status", "amount", "provider_reference", "order_id", "failure_reason"),
    ),
    EvidencePurpose.COUPON_STATUS: PurposeSpec(
        "COUPON_CATALOG",
        EvidenceEntityType.COUPON,
        "coupon_id",
        "coupon_evidence",
        ("code", "status", "expires_at", "is_active"),
    ),
    EvidencePurpose.COUPON_ELIGIBILITY: PurposeSpec(
        "COUPON_CATALOG",
        EvidenceEntityType.COUPON,
        "coupon_id",
        "coupon_evidence",
        (
            "code",
            "status",
            "discount_type",
            "discount_value",
            "min_cart_total",
            "allowed_category",
        ),
    ),
    EvidencePurpose.CART_STATUS: PurposeSpec(
        "CART",
        EvidenceEntityType.CART,
        "cart_id",
        "cart_evidence",
        ("status", "coupon_code", "subtotal", "discount_total", "total", "item_count"),
    ),
    EvidencePurpose.RETURN_STATUS: PurposeSpec(
        "RETURN_LEDGER",
        EvidenceEntityType.RETURN,
        "order_id",
        "return_evidence",
        (
            "order_id",
            "return_code",
            "return_status",
            "refund_status",
            "return_tracking_no",
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    purpose: EvidencePurpose
    entity_type: EvidenceEntityType
    entity_id: int
    source: str
    record_id: int
    data: dict
    owner_user_id: int | None = None


class EvidenceFetcherAdapter(Protocol):
    async def fetch(
        self,
        purpose: EvidencePurpose,
        entity_id: int,
        user_id: int,
    ) -> EvidenceRecord | None: ...


class InMemoryEvidenceFetcherAdapter:
    """Read-only adapter for contract tests and future DB adapter replacement."""

    def __init__(self, records: list[EvidenceRecord] | None = None) -> None:
        self._records = tuple(records or [])

    async def fetch(
        self,
        purpose: EvidencePurpose,
        entity_id: int,
        user_id: int,
    ) -> EvidenceRecord | None:
        return next(
            (
                record
                for record in self._records
                if record.purpose == purpose
                and record.entity_id == entity_id
                and (
                    record.owner_user_id is None
                    or record.owner_user_id == user_id
                )
            ),
            None,
        )


class EvidenceFetcher:
    """Fetches only requested, resolved, structured evidence without fallback."""

    def __init__(self, adapter: EvidenceFetcherAdapter) -> None:
        self.adapter = adapter

    async def fetch(
        self, fetcher_input: EvidenceFetcherInput | dict
    ) -> EvidenceFetcherOutput:
        request = (
            fetcher_input
            if isinstance(fetcher_input, EvidenceFetcherInput)
            else EvidenceFetcherInput.model_validate(fetcher_input)
        )
        output = EvidenceFetcherOutput()
        resolved = request.data_resolution.resolved_entities
        for required_context in request.required_contexts:
            purpose = self._purpose(required_context, output)
            if purpose is None:
                continue
            spec = PURPOSE_SPECS[purpose]
            if not self._contract_matches(required_context, spec, output):
                continue
            entity_id = getattr(resolved, spec.resolved_id_field)
            if entity_id is None:
                output.missing_evidence.append(
                    MissingEvidence(
                        source=spec.source,
                        entity_type=spec.entity_type,
                        purpose=purpose.value,
                        reason=f"{spec.resolved_id_field.upper()}_MISSING",
                    )
                )
                continue
            record = await self.adapter.fetch(purpose, entity_id, request.user_id)
            if record is None:
                output.missing_evidence.append(
                    MissingEvidence(
                        source=spec.source,
                        entity_type=spec.entity_type,
                        purpose=purpose.value,
                        reason="EVIDENCE_NOT_FOUND",
                    )
                )
                continue
            if record.source != spec.source or record.entity_type != spec.entity_type:
                output.missing_evidence.append(
                    MissingEvidence(
                        source=spec.source,
                        entity_type=spec.entity_type,
                        purpose=purpose.value,
                        reason="EVIDENCE_CONTRACT_MISMATCH",
                    )
                )
                output.warnings.append(
                    f"EVIDENCE_CONTRACT_MISMATCH:{purpose.value}"
                )
                continue
            data = {
                field: record.data[field]
                for field in self._requested_fields(required_context, spec)
                if field in record.data
            }
            item = EvidenceItem(
                source=spec.source,
                entity_type=spec.entity_type,
                entity_id=entity_id,
                purpose=purpose,
                data=data,
                provenance=EvidenceProvenance(
                    source=record.source,
                    record_id=record.record_id,
                ),
            )
            getattr(output, spec.output_field).append(item)
        return output

    @staticmethod
    def _purpose(
        required_context: RequiredContext, output: EvidenceFetcherOutput
    ) -> EvidencePurpose | None:
        try:
            return EvidencePurpose(required_context.purpose.strip().upper())
        except ValueError:
            output.warnings.append(
                f"UNKNOWN_PURPOSE:{required_context.purpose.strip()}"
            )
            return None

    @staticmethod
    def _contract_matches(
        required_context: RequiredContext,
        spec: PurposeSpec,
        output: EvidenceFetcherOutput,
    ) -> bool:
        if required_context.source and required_context.source != spec.source:
            output.warnings.append(
                f"SOURCE_MISMATCH:{required_context.purpose}"
            )
            return False
        if (
            required_context.entity_type
            and required_context.entity_type != spec.entity_type
        ):
            output.warnings.append(
                f"ENTITY_TYPE_MISMATCH:{required_context.purpose}"
            )
            return False
        return True

    @staticmethod
    def _requested_fields(
        required_context: RequiredContext, spec: PurposeSpec
    ) -> tuple[str, ...]:
        if not required_context.fields_hint:
            return spec.allowed_fields
        requested = set(required_context.fields_hint)
        return tuple(field for field in spec.allowed_fields if field in requested)
