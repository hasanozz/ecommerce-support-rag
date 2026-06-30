from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    DemoCart,
    DemoCartItem,
    DemoCoupon,
    DemoOrder,
    DemoPaymentAttempt,
    DemoProduct,
    DemoReturnRequest,
)

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
        "return_id",
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


REQUIRED_FIELD_GROUPS: dict[EvidencePurpose, tuple[tuple[str, ...], ...]] = {
    EvidencePurpose.PRODUCT_CAPACITY: (("capacity_ml", "volume_ml"),),
    EvidencePurpose.PRODUCT_PRICE: (("price",), ("currency",)),
    EvidencePurpose.PRODUCT_STOCK: (("stock",), ("availability",)),
    EvidencePurpose.ORDER_STATUS: (("order_status",),),
    EvidencePurpose.ORDER_SHIPPING_STATUS: (("shipping_status",),),
    EvidencePurpose.PAYMENT_STATUS: (("status",),),
    EvidencePurpose.PAYMENT_WITHOUT_ORDER: (("status",),),
    EvidencePurpose.COUPON_STATUS: (("status",),),
    EvidencePurpose.CART_STATUS: (("status",),),
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


class SqlAlchemyEvidenceFetcherAdapter:
    """Read-only ID-based evidence adapter for existing commerce models."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def bind(self, session: AsyncSession) -> "SqlAlchemyEvidenceFetcherAdapter":
        return SqlAlchemyEvidenceFetcherAdapter(session)

    async def fetch(
        self,
        purpose: EvidencePurpose,
        entity_id: int,
        user_id: int,
    ) -> EvidenceRecord | None:
        if self.session is None:
            raise RuntimeError("SQL evidence adapter is not bound to a session")
        if purpose in {
            EvidencePurpose.PRODUCT_CAPACITY,
            EvidencePurpose.PRODUCT_PRICE,
            EvidencePurpose.PRODUCT_STOCK,
            EvidencePurpose.PRODUCT_RETURN_ELIGIBILITY,
        }:
            return await self._product(purpose, entity_id)
        if purpose in {
            EvidencePurpose.ORDER_STATUS,
            EvidencePurpose.ORDER_CANCEL_ELIGIBILITY,
            EvidencePurpose.ORDER_SHIPPING_STATUS,
        }:
            return await self._order(purpose, entity_id, user_id)
        if purpose in {
            EvidencePurpose.PAYMENT_STATUS,
            EvidencePurpose.PAYMENT_WITHOUT_ORDER,
        }:
            return await self._payment(purpose, entity_id, user_id)
        if purpose in {
            EvidencePurpose.COUPON_STATUS,
            EvidencePurpose.COUPON_ELIGIBILITY,
        }:
            return await self._coupon(purpose, entity_id)
        if purpose == EvidencePurpose.CART_STATUS:
            return await self._cart(purpose, entity_id, user_id)
        if purpose == EvidencePurpose.RETURN_STATUS:
            return await self._return(purpose, entity_id, user_id)
        return None

    async def _product(
        self, purpose: EvidencePurpose, product_id: int
    ) -> EvidenceRecord | None:
        product = await self.session.scalar(
            select(DemoProduct).where(
                DemoProduct.id == product_id,
                DemoProduct.is_active.is_(True),
            )
        )
        if product is None:
            return None
        attributes = product.attributes or {}
        data: dict = {}
        if purpose == EvidencePurpose.PRODUCT_CAPACITY:
            data["name"] = product.name
            capacity = next(
                (
                    attributes[key]
                    for key in ("capacity_ml", "volume_ml", "hacim_ml")
                    if attributes.get(key) is not None
                ),
                None,
            )
            if capacity is not None:
                data["capacity_ml"] = capacity
                data["volume_ml"] = capacity
        elif purpose == EvidencePurpose.PRODUCT_PRICE:
            data = {"price": product.price, "currency": product.currency}
        elif purpose == EvidencePurpose.PRODUCT_STOCK:
            data = {
                "stock": product.stock,
                "availability": "IN_STOCK" if product.stock > 0 else "OUT_OF_STOCK",
            }
        elif purpose == EvidencePurpose.PRODUCT_RETURN_ELIGIBILITY:
            data = {
                "returnable": product.returnable,
                "return_policy_note": product.return_policy_note,
                "category": product.category,
            }
        return self._record(
            purpose, EvidenceEntityType.PRODUCT, product_id, "PRODUCT_CATALOG", data
        )

    async def _order(
        self, purpose: EvidencePurpose, order_id: int, user_id: int
    ) -> EvidenceRecord | None:
        order = await self.session.scalar(
            select(DemoOrder)
            .options(selectinload(DemoOrder.shipment))
            .where(DemoOrder.id == order_id, DemoOrder.user_id == user_id)
        )
        if order is None:
            return None
        data = {
            "order_no": order.order_no,
            "order_status": order.order_status,
            "shipping_status": order.shipping_status,
            "payment_status": order.payment_status,
        }
        if purpose == EvidencePurpose.ORDER_SHIPPING_STATUS and order.shipment:
            data.update(
                {
                    "tracking_number": order.shipment.tracking_number,
                    "estimated_delivery_at": order.shipment.estimated_delivery_at,
                    "delay_reason": order.shipment.delay_reason,
                }
            )
        return self._record(
            purpose,
            EvidenceEntityType.ORDER,
            order_id,
            "ORDER_LEDGER",
            data,
            owner_user_id=user_id,
        )

    async def _payment(
        self, purpose: EvidencePurpose, payment_id: int, user_id: int
    ) -> EvidenceRecord | None:
        payment = await self.session.scalar(
            select(DemoPaymentAttempt).where(
                DemoPaymentAttempt.id == payment_id,
                DemoPaymentAttempt.user_id == user_id,
            )
        )
        if payment is None:
            return None
        data = {
            "status": payment.status,
            "amount": payment.amount,
            "provider_reference": payment.provider_reference,
            "order_id": payment.order_id,
        }
        if purpose == EvidencePurpose.PAYMENT_WITHOUT_ORDER:
            data["failure_reason"] = payment.failure_reason
        return self._record(
            purpose,
            EvidenceEntityType.PAYMENT,
            payment_id,
            "PAYMENT_LEDGER",
            data,
            owner_user_id=user_id,
        )

    async def _coupon(
        self, purpose: EvidencePurpose, coupon_id: int
    ) -> EvidenceRecord | None:
        coupon = await self.session.scalar(
            select(DemoCoupon).where(DemoCoupon.id == coupon_id)
        )
        if coupon is None:
            return None
        data = {
            "code": coupon.code,
            "status": coupon.status,
            "expires_at": coupon.expires_at,
            "is_active": coupon.is_active,
        }
        if purpose == EvidencePurpose.COUPON_ELIGIBILITY:
            data.update(
                {
                    "discount_type": coupon.discount_type,
                    "discount_value": coupon.discount_value,
                    "min_cart_total": coupon.min_cart_total,
                    "allowed_category": coupon.allowed_category,
                }
            )
        return self._record(
            purpose,
            EvidenceEntityType.COUPON,
            coupon_id,
            "COUPON_CATALOG",
            data,
        )

    async def _cart(
        self, purpose: EvidencePurpose, cart_id: int, user_id: int
    ) -> EvidenceRecord | None:
        cart = await self.session.scalar(
            select(DemoCart)
            .options(selectinload(DemoCart.items).selectinload(DemoCartItem.product))
            .where(DemoCart.id == cart_id, DemoCart.user_id == user_id)
        )
        if cart is None:
            return None
        return self._record(
            purpose,
            EvidenceEntityType.CART,
            cart_id,
            "CART",
            {
                "status": cart.status,
                "coupon_code": cart.coupon_code,
                "subtotal": cart.subtotal,
                "discount_total": cart.discount_total,
                "total": cart.total,
                "item_count": len(cart.items),
            },
            owner_user_id=user_id,
        )

    async def _return(
        self, purpose: EvidencePurpose, return_id: int, user_id: int
    ) -> EvidenceRecord | None:
        return_request = await self.session.scalar(
            select(DemoReturnRequest).where(
                DemoReturnRequest.id == return_id,
                DemoReturnRequest.user_id == user_id,
            )
        )
        if return_request is None:
            return None
        return EvidenceRecord(
            purpose=purpose,
            entity_type=EvidenceEntityType.RETURN,
            entity_id=return_id,
            source="RETURN_LEDGER",
            record_id=return_request.id,
            data={
                "order_id": return_request.order_id,
                "return_code": return_request.return_code,
                "return_status": return_request.return_status,
                "refund_status": return_request.refund_status,
                "return_tracking_no": return_request.return_tracking_no,
            },
            owner_user_id=user_id,
        )

    @staticmethod
    def _record(
        purpose: EvidencePurpose,
        entity_type: EvidenceEntityType,
        entity_id: int,
        source: str,
        data: dict,
        owner_user_id: int | None = None,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            purpose=purpose,
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            record_id=entity_id,
            data=data,
            owner_user_id=owner_user_id,
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
            missing_groups = [
                group
                for group in REQUIRED_FIELD_GROUPS.get(purpose, ())
                if not any(field in data and data[field] is not None for field in group)
            ]
            if missing_groups:
                output.missing_evidence.append(
                    MissingEvidence(
                        source=spec.source,
                        entity_type=spec.entity_type,
                        purpose=purpose.value,
                        reason="REQUIRED_FIELDS_MISSING",
                    )
                )
                output.warnings.append(f"EVIDENCE_FIELDS_MISSING:{purpose.value}")
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
