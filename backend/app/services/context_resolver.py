from __future__ import annotations

from dataclasses import dataclass

from ..schemas.context_resolver import (
    ContextIntent,
    ContextResolverInput,
    ContextResolverOutput,
    ResolvedEntities,
)


USED_CONVERSATION_STATE = "USED_CONVERSATION_STATE"


@dataclass(frozen=True, slots=True)
class IntentPlan:
    data_sources: tuple[str, ...]
    fields: tuple[str, ...]
    needs_support_rag: bool
    entity_kind: str | None = None


INTENT_PLANS: dict[ContextIntent, IntentPlan] = {
    ContextIntent.PRODUCT_ATTRIBUTE: IntentPlan(
        ("product_db",), ("attributes", "description"), False, "product"
    ),
    ContextIntent.PRODUCT_STOCK: IntentPlan(
        ("product_db",), ("stock", "availability"), False, "product"
    ),
    ContextIntent.PRODUCT_PRICE: IntentPlan(
        ("product_db",), ("price", "discounted_price", "currency"), False, "product"
    ),
    ContextIntent.PRODUCT_REVIEWS: IntentPlan(
        ("product_db", "review_db"),
        ("rating_average", "review_count", "reviews"),
        False,
        "product",
    ),
    ContextIntent.PRODUCT_RETURN_ELIGIBILITY: IntentPlan(
        ("product_db",),
        ("returnable", "return_policy_note", "category"),
        True,
        "product",
    ),
    ContextIntent.ORDER_STATUS: IntentPlan(
        ("order_db",), ("order_status", "shipping_status"), False, "order"
    ),
    ContextIntent.ORDER_CANCEL: IntentPlan(
        ("order_db",),
        ("order_status", "shipping_status", "cancel_eligibility"),
        True,
        "order",
    ),
    ContextIntent.ORDER_SHIPPING_DELAY: IntentPlan(
        ("order_db",),
        ("shipping_status", "estimated_delivery_at", "delay_reason", "tracking_number"),
        True,
        "order",
    ),
    ContextIntent.DELIVERED_NOT_RECEIVED: IntentPlan(
        ("order_db",),
        ("shipping_status", "delivered_at", "tracking_number", "carrier"),
        True,
        "order",
    ),
    ContextIntent.RETURN_CREATE: IntentPlan(
        ("order_db", "return_db"),
        ("order_status", "returnable", "return_status"),
        True,
        "order",
    ),
    ContextIntent.PAYMENT_CHARGED_ORDER_NOT_CREATED: IntentPlan(
        ("payment_db", "order_db"),
        ("payment_status", "amount", "provider_reference", "order_id"),
        True,
    ),
    ContextIntent.COUPON_INVALID: IntentPlan(
        ("coupon_db", "cart_db"),
        ("status", "expires_at", "min_cart_total", "allowed_category", "cart_total"),
        True,
        "coupon",
    ),
    ContextIntent.COUPON_EXPIRED: IntentPlan(
        ("coupon_db", "cart_db"),
        ("status", "expires_at", "is_active"),
        True,
        "coupon",
    ),
    ContextIntent.CAMPAIGN_USAGE: IntentPlan(
        ("campaign_db", "cart_db"),
        ("status", "usage_conditions", "eligible_categories", "cart_total"),
        False,
    ),
    ContextIntent.SUPPORT_POLICY_ONLY: IntentPlan((), (), True),
}


FALLBACK_REASONS = {
    ContextIntent.OUT_OF_DOMAIN: "OUT_OF_DOMAIN",
    ContextIntent.UNCLEAR: "UNCLEAR_INTENT",
    ContextIntent.UNSAFE: "UNSAFE_REQUEST",
}


class ContextResolver:
    """Plans required context without fetching data or invoking an LLM/RAG."""

    def resolve(self, resolver_input: ContextResolverInput | dict) -> ContextResolverOutput:
        request = (
            resolver_input
            if isinstance(resolver_input, ContextResolverInput)
            else ContextResolverInput.model_validate(resolver_input)
        )
        classifier = request.classifier_output
        intent_value = classifier.intent.strip().upper()
        try:
            intent = ContextIntent(intent_value)
        except ValueError:
            return self._fallback(request, "UNSUPPORTED_INTENT")

        if intent in FALLBACK_REASONS:
            return self._fallback(request, FALLBACK_REASONS[intent])

        plan = INTENT_PLANS[intent]
        fields = list(plan.fields)
        if (
            intent == ContextIntent.PRODUCT_ATTRIBUTE
            and (classifier.requested_info or "").strip().casefold() == "capacity"
        ):
            fields = ["capacity_ml", "volume_ml", "description"]

        needs_support_rag = plan.needs_support_rag
        if intent == ContextIntent.CAMPAIGN_USAGE:
            requested_info = (classifier.requested_info or "").strip().casefold()
            needs_support_rag = requested_info in {
                "policy",
                "usage_policy",
                "conditions",
            } or bool(classifier.doc_id)

        entities = classifier.entities
        resolved = ResolvedEntities(
            product_id=entities.product_id,
            product_name=self._clean(entities.product_name),
            order_id=entities.order_id,
            order_no=self._clean(entities.order_no),
            coupon_code=self._clean(entities.coupon_code),
            category=self._clean(entities.category or classifier.category),
        )
        warnings: list[str] = []
        clarification_reason = self._resolve_required_entity(
            plan.entity_kind, resolved, request, warnings
        )

        support_doc_ids = (
            [classifier.doc_id.strip()]
            if needs_support_rag and classifier.doc_id and classifier.doc_id.strip()
            else []
        )
        return ContextResolverOutput(
            resolved_entities=resolved,
            data_sources=list(plan.data_sources),
            fields=fields,
            needs_support_rag=needs_support_rag,
            support_doc_ids=support_doc_ids,
            needs_clarification=clarification_reason is not None,
            clarification_reason=clarification_reason,
            fallback_reason=None,
            next_step="CLARIFY" if clarification_reason else "FETCH_CONTEXT",
            confidence=classifier.confidence,
            warnings=warnings,
        )

    def _resolve_required_entity(
        self,
        entity_kind: str | None,
        resolved: ResolvedEntities,
        request: ContextResolverInput,
        warnings: list[str],
    ) -> str | None:
        state = request.conversation_state
        if entity_kind == "product":
            if resolved.product_id is not None:
                return None
            if resolved.product_name:
                # TODO(integration): resolve this exact name through an injected lookup.
                return "PRODUCT_NAME_COULD_NOT_BE_RESOLVED"
            if state.last_product_id is not None:
                resolved.product_id = state.last_product_id
                warnings.append(USED_CONVERSATION_STATE)
                return None
            return "PRODUCT_CONTEXT_REQUIRED"

        if entity_kind == "order":
            if resolved.order_id is not None:
                return None
            if resolved.order_no or resolved.product_name:
                # A product mention is not proof that any particular order is intended.
                return "ORDER_REFERENCE_COULD_NOT_BE_RESOLVED"
            if state.last_order_id is not None:
                resolved.order_id = state.last_order_id
                warnings.append(USED_CONVERSATION_STATE)
                return None
            return "ORDER_CONTEXT_REQUIRED"

        if entity_kind == "coupon" and not resolved.coupon_code:
            return "COUPON_CODE_REQUIRED"
        return None

    def _fallback(
        self, request: ContextResolverInput, reason: str
    ) -> ContextResolverOutput:
        entities = request.classifier_output.entities
        return ContextResolverOutput(
            resolved_entities=ResolvedEntities(
                product_id=entities.product_id,
                product_name=self._clean(entities.product_name),
                order_id=entities.order_id,
                order_no=self._clean(entities.order_no),
                coupon_code=self._clean(entities.coupon_code),
                category=self._clean(entities.category),
            ),
            data_sources=[],
            fields=[],
            needs_support_rag=False,
            support_doc_ids=[],
            needs_clarification=False,
            clarification_reason=None,
            fallback_reason=reason,
            next_step="FALLBACK",
            confidence=request.classifier_output.confidence,
            warnings=[],
        )

    @staticmethod
    def _clean(value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None
