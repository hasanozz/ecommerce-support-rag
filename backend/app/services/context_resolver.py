from __future__ import annotations

from dataclasses import dataclass

from ..schemas.context_resolver import (
    ContextIntent,
    ContextResolverInput,
    ContextResolverOutput,
    ResolvedEntities,
)
from .context_planner import is_read_only_order_shipping_intent, should_use_rag


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
        if self._has_router_signals(classifier):
            return self._resolve_router_plan(request)
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
            plan.entity_kind,
            resolved,
            request,
            warnings,
            intent=intent_value,
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

    @staticmethod
    def _has_router_signals(classifier) -> bool:
        return bool(
            classifier.expected_action
            or classifier.priority
            or classifier.requested_information
            or classifier.routing_hints
        )

    def _resolve_router_plan(
        self, request: ContextResolverInput
    ) -> ContextResolverOutput:
        classifier = request.classifier_output
        domain = (classifier.domain or "").strip().upper()
        category = (classifier.category or "").strip().upper() or "GENEL_DESTEK"
        intent = (classifier.intent or "").strip().upper()
        requested_information = [
            str(item).strip().casefold()
            for item in classifier.requested_information
            if str(item).strip()
        ]
        requested_info = (classifier.requested_info or "").strip().casefold()
        hints = classifier.routing_hints or {}

        if domain in {"OUT_OF_DOMAIN", "UNSAFE", "NONSENSE"} or (
            classifier.expected_action or ""
        ).strip().upper() == "REJECT":
            return self._fallback(
                request, "UNSAFE_REQUEST" if domain == "UNSAFE" else "OUT_OF_DOMAIN"
            )

        if domain == "MIXED":
            return self._router_mixed_plan(
                request,
                category,
                intent,
                requested_information,
                requested_info,
                hints,
            )
        if domain == "PRODUCT" or intent.startswith("PRODUCT_"):
            return self._router_product_plan(
                request,
                category,
                intent,
                requested_information,
                requested_info,
                hints,
            )
        if domain == "SUPPORT":
            return self._router_support_plan(
                request,
                category,
                intent,
                requested_information,
                requested_info,
                hints,
            )

        try:
            legacy_intent = ContextIntent(intent)
        except ValueError:
            return self._fallback(request, "UNSUPPORTED_INTENT")
        if legacy_intent in FALLBACK_REASONS:
            return self._fallback(request, FALLBACK_REASONS[legacy_intent])
        plan = INTENT_PLANS[legacy_intent]
        resolved = self._resolved_entities(classifier, category)
        fields = list(plan.fields)
        if (
            legacy_intent == ContextIntent.PRODUCT_ATTRIBUTE
            and requested_info == "capacity"
        ):
            fields = ["capacity_ml", "volume_ml", "description"]
        needs_support_rag = plan.needs_support_rag or bool(hints.get("rag_needed"))
        if legacy_intent == ContextIntent.CAMPAIGN_USAGE:
            needs_support_rag = (
                requested_info in {"policy", "usage_policy", "conditions"}
                or bool(classifier.doc_id)
                or bool(hints.get("rag_needed"))
            )
        warnings: list[str] = []
        clarification_reason = self._resolve_required_entity(
            plan.entity_kind,
            resolved,
            request,
            warnings,
            intent=legacy_intent.value,
        )
        return ContextResolverOutput(
            resolved_entities=resolved,
            data_sources=list(plan.data_sources),
            fields=fields,
            needs_support_rag=needs_support_rag,
            support_doc_ids=(
                [classifier.doc_id.strip()]
                if needs_support_rag and classifier.doc_id and classifier.doc_id.strip()
                else []
            ),
            needs_clarification=clarification_reason is not None,
            clarification_reason=clarification_reason,
            fallback_reason=None,
            next_step="CLARIFY" if clarification_reason else "FETCH_CONTEXT",
            confidence=classifier.confidence,
            warnings=warnings,
        )

    def _router_product_plan(
        self,
        request: ContextResolverInput,
        category: str,
        intent: str,
        requested_information: list[str],
        requested_info: str,
        hints: dict,
    ) -> ContextResolverOutput:
        classifier = request.classifier_output
        resolved = self._resolved_entities(classifier, category)
        warnings: list[str] = []
        fields = self._product_fields(requested_information, requested_info)
        if resolved.product_id is None and not resolved.product_name:
            if request.conversation_state.last_product_id is not None:
                resolved.product_id = request.conversation_state.last_product_id
                warnings.append(USED_CONVERSATION_STATE)
            else:
                return ContextResolverOutput(
                    resolved_entities=resolved,
                    data_sources=["product_db"],
                    fields=fields,
                    needs_support_rag=bool(hints.get("rag_needed"))
                    or intent == "PRODUCT_RETURN_ELIGIBILITY"
                    or requested_info in {"policy", "eligibility"},
                    support_doc_ids=[],
                    needs_clarification=True,
                    clarification_reason="PRODUCT_CONTEXT_REQUIRED",
                    fallback_reason=None,
                    next_step="CLARIFY",
                    confidence=classifier.confidence,
                    warnings=warnings,
                )
        needs_support_rag = bool(hints.get("rag_needed")) or intent == "PRODUCT_RETURN_ELIGIBILITY" or requested_info in {
            "policy",
            "eligibility",
        }
        return ContextResolverOutput(
            resolved_entities=resolved,
            data_sources=["product_db"],
            fields=fields,
            needs_support_rag=needs_support_rag,
            support_doc_ids=(
                [classifier.doc_id.strip()]
                if needs_support_rag and classifier.doc_id and classifier.doc_id.strip()
                else []
            ),
            needs_clarification=False,
            clarification_reason=None,
            fallback_reason=None,
            next_step="FETCH_CONTEXT",
            confidence=classifier.confidence,
            warnings=warnings,
        )

    def _router_support_plan(
        self,
        request: ContextResolverInput,
        category: str,
        intent: str,
        requested_information: list[str],
        requested_info: str,
        hints: dict,
    ) -> ContextResolverOutput:
        classifier = request.classifier_output
        resolved = self._resolved_entities(classifier, category)
        data_sources, fields, entity_kind = self._support_plan(
            category, intent, requested_information, requested_info
        )
        warnings: list[str] = []
        clarification_reason = self._resolve_required_entity(
            entity_kind,
            resolved,
            request,
            warnings,
            intent=intent,
        )
        needs_support_rag = should_use_rag(classifier.domain, intent, hints) or requested_info in {
            "policy",
            "procedure",
            "eligibility",
        }
        return ContextResolverOutput(
            resolved_entities=resolved,
            data_sources=list(data_sources),
            fields=list(fields),
            needs_support_rag=needs_support_rag,
            support_doc_ids=(
                [classifier.doc_id.strip()]
                if needs_support_rag and classifier.doc_id and classifier.doc_id.strip()
                else []
            ),
            needs_clarification=clarification_reason is not None,
            clarification_reason=clarification_reason,
            fallback_reason=None,
            next_step="CLARIFY" if clarification_reason else "FETCH_CONTEXT",
            confidence=classifier.confidence,
            warnings=warnings,
        )

    def _router_mixed_plan(
        self,
        request: ContextResolverInput,
        category: str,
        intent: str,
        requested_information: list[str],
        requested_info: str,
        hints: dict,
    ) -> ContextResolverOutput:
        product_plan = self._router_product_plan(
            request, category, intent, requested_information, requested_info, hints
        )
        support_plan = self._router_support_plan(
            request, category, intent, requested_information, requested_info, hints
        )
        data_sources = list(
            dict.fromkeys(product_plan.data_sources + support_plan.data_sources)
        )
        fields = list(dict.fromkeys(product_plan.fields + support_plan.fields))
        warnings = list(dict.fromkeys(product_plan.warnings + support_plan.warnings))
        support_doc_ids = list(
            dict.fromkeys(product_plan.support_doc_ids + support_plan.support_doc_ids)
        )
        return ContextResolverOutput(
            resolved_entities=product_plan.resolved_entities,
            data_sources=data_sources,
            fields=fields,
            needs_support_rag=product_plan.needs_support_rag
            or support_plan.needs_support_rag
            or bool(hints.get("rag_needed")),
            support_doc_ids=support_doc_ids,
            needs_clarification=product_plan.needs_clarification
            or support_plan.needs_clarification,
            clarification_reason=product_plan.clarification_reason
            or support_plan.clarification_reason,
            fallback_reason=None,
            next_step=(
                "CLARIFY"
                if (product_plan.needs_clarification or support_plan.needs_clarification)
                else "FETCH_CONTEXT"
            ),
            confidence=product_plan.confidence,
            warnings=warnings,
        )

    @staticmethod
    def _product_fields(
        requested_information: list[str], requested_info: str
    ) -> list[str]:
        if requested_info == "price" or "price" in requested_information:
            return ["price", "discounted_price", "currency"]
        if requested_info == "stock" or "stock" in requested_information:
            return ["stock", "availability"]
        if requested_info == "reviews" or "reviews" in requested_information:
            return ["rating_average", "review_count", "reviews"]
        if requested_info in {"capacity", "power", "watt", "motor_power", "motor_gucu"} or any(
            item in {"capacity", "power", "watt", "motor_power", "motor_gucu"}
            for item in requested_information
        ):
            return ["capacity_ml", "volume_ml", "description"]
        if requested_info == "warranty" or "warranty" in requested_information:
            return ["warranty_months", "warranty_note"]
        if requested_info in {"policy", "eligibility"} or any(
            item in {"policy", "eligibility"} for item in requested_information
        ):
            return ["returnable", "return_policy_note", "category"]
        return ["name", "brand", "category", "subcategory", "description"]

    @staticmethod
    def _support_plan(
        category: str,
        intent: str,
        requested_information: list[str],
        requested_info: str,
    ) -> tuple[tuple[str, ...], list[str], str | None]:
        intent_value = intent.strip().upper()
        if category == "IADE":
            if intent_value == "RETURN_CREATE":
                return (
                    ("order_db", "return_db"),
                    ["order_status", "return_status", "returnable", "return_policy_note"],
                    "order",
                )
            return (
                ("order_db", "return_db"),
                ["order_status", "return_status", "returnable", "return_policy_note"],
                None,
            )
        if category == "ODEME":
            return (
                ("payment_db", "order_db"),
                ["payment_status", "amount", "provider_reference", "order_id"],
                None,
            )
        if category == "KARGO_TESLIMAT":
            if is_read_only_order_shipping_intent(intent, None):
                return (
                    ("order_db", "shipment_db"),
                    [
                        "order_status",
                        "shipping_status",
                        "tracking_number",
                        "estimated_delivery_at",
                        "delay_reason",
                    ],
                    None,
                )
            return (
                ("order_db", "shipment_db"),
                [
                    "order_status",
                    "shipping_status",
                    "tracking_number",
                    "estimated_delivery_at",
                    "delay_reason",
                ],
                "order",
            )
        if category == "KAMPANYA_PUAN":
            return (
                ("coupon_db", "cart_db"),
                ["status", "expires_at", "min_cart_total", "allowed_category", "cart_total"],
                None,
            )
        if category == "SIPARIS":
            if is_read_only_order_shipping_intent(intent, None):
                return (
                    ("order_db", "shipment_db"),
                    ["order_status", "shipping_status", "order_no"],
                    None,
                )
            return (
                ("order_db", "shipment_db"),
                ["order_status", "shipping_status", "order_no"],
                "order",
            )
        if category == "HESAP_GUVENLIK":
            return ((), ["security_status", "risk_note"], None)
        if intent.startswith("RETURN_"):
            if intent_value in {
                "RETURN_POLICY",
                "RETURN_SHIPPING_PROCESS",
                "RETURN_REJECTION_REASON",
                "RETURN_REFUND_TIMING",
                "USED_PRODUCT_RETURN",
                "UNOPENED_PRODUCT_RETURN",
                "PRODUCT_RETURNABILITY",
                "PRODUCT_WARRANTY_COVERAGE",
                "DEFECTIVE_OR_DAMAGED_PRODUCT_RETURN",
                "POINT_STATUS_AFTER_RETURN",
            }:
                return (
                    ("order_db", "return_db", "product_db"),
                    ["order_status", "return_status", "returnable", "return_policy_note"],
                    None,
                )
            return (
                ("order_db", "return_db"),
                ["order_status", "return_status", "returnable", "return_policy_note"],
                "order",
            )
        return (
            ("order_db",),
            ["order_status", "shipping_status", "payment_status", "order_no"],
            None,
        )

    @staticmethod
    def _resolved_entities(
        classifier, category: str
    ) -> ResolvedEntities:
        entities = classifier.entities
        return ResolvedEntities(
            product_id=entities.product_id,
            product_name=ContextResolver._clean(entities.product_name),
            order_id=entities.order_id,
            order_no=ContextResolver._clean(entities.order_no),
            coupon_code=ContextResolver._clean(entities.coupon_code),
            category=ContextResolver._clean(entities.category or category),
        )

    def _resolve_required_entity(
        self,
        entity_kind: str | None,
        resolved: ResolvedEntities,
        request: ContextResolverInput,
        warnings: list[str],
        *,
        intent: str | None = None,
    ) -> str | None:
        state = request.conversation_state
        if entity_kind == "product":
            if resolved.product_id is not None:
                return None
            if resolved.product_name:
                # Data Resolver owns product_name -> product_id resolution.
                return None
            if state.last_product_id is not None:
                resolved.product_id = state.last_product_id
                warnings.append(USED_CONVERSATION_STATE)
                return None
            return "PRODUCT_CONTEXT_REQUIRED"

        if entity_kind == "order":
            if is_read_only_order_shipping_intent(intent, request.classifier_output.subcategory):
                return None
            if resolved.order_id is not None:
                return None
            if resolved.order_no:
                # Data Resolver owns order_no -> order_id resolution.
                return None
            if resolved.product_name:
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
