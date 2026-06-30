from types import SimpleNamespace

from backend.app.services.classifier import ClassificationResult
from backend.app.services.context_resolver import USED_CONVERSATION_STATE
from backend.app.services.pipeline import SupportPipeline


def classification(intent: str, *, expected_action: str = "RAG_ANSWER"):
    return ClassificationResult(
        category="SIPARIS",
        subcategory="",
        priority="MEDIUM",
        expected_action=expected_action,
        confidence=0.8,
        intent=intent,
    )


def resolve_with_pipeline(
    intent: str,
    message: str,
    *,
    state=None,
    expected_action: str = "RAG_ANSWER",
    is_in_scope: bool = True,
):
    pipeline = SupportPipeline()
    resolver_input = pipeline._context_resolver_input(
        classification(intent, expected_action=expected_action),
        message,
        canonical_query=message,
        is_in_scope=is_in_scope,
        conversation_state=state,
        frontend_context={},
        followup_reference={},
    )
    return pipeline, pipeline.context_resolver.resolve(resolver_input)


def test_pipeline_maps_out_of_domain_to_resolver_fallback():
    _, plan = resolve_with_pipeline(
        "OUT_OF_DOMAIN", "yarın hava nasıl?", is_in_scope=False
    )

    assert plan.next_step == "FALLBACK"
    assert plan.fallback_reason == "OUT_OF_DOMAIN"


def test_pipeline_maps_unclear_to_resolver_fallback():
    _, plan = resolve_with_pipeline(
        "UNCLEAR", "yardım", expected_action="ASK_CLARIFICATION"
    )

    assert plan.next_step == "FALLBACK"
    assert plan.fallback_reason == "UNCLEAR_INTENT"


def test_pipeline_product_followup_uses_last_product_state():
    state = SimpleNamespace(
        last_product_id=31,
        last_order_id=None,
        last_intent="PRODUCT_ATTRIBUTE",
        last_action="show_technical_details",
    )
    _, plan = resolve_with_pipeline("PRODUCT_STOCK", "stokta mı?", state=state)

    assert plan.resolved_entities.product_id == 31
    assert plan.next_step == "FETCH_CONTEXT"
    assert USED_CONVERSATION_STATE in plan.warnings


def test_pipeline_product_followup_without_state_clarifies():
    _, plan = resolve_with_pipeline("PRODUCT_REVIEWS", "yorumları nasıl?")

    assert plan.next_step == "CLARIFY"
    assert plan.needs_clarification is True
    assert plan.clarification_reason == "PRODUCT_CONTEXT_REQUIRED"


def test_pipeline_product_attribute_skips_support_rag():
    state = SimpleNamespace(last_product_id=4)
    pipeline, plan = resolve_with_pipeline(
        "PRODUCT_ATTRIBUTE", "kaç ml?", state=state
    )

    assert plan.needs_support_rag is False
    assert pipeline._should_run_support_rag(
        needs_support_rag=plan.needs_support_rag,
        support_in_scope=True,
        route_mode="followup_resolved",
    ) is False


def test_pipeline_product_return_eligibility_keeps_support_rag():
    state = SimpleNamespace(last_product_id=7)
    pipeline, plan = resolve_with_pipeline(
        "PRODUCT_RETURN_ELIGIBILITY", "bu ürün iade olur mu?", state=state
    )

    assert plan.needs_support_rag is True
    assert pipeline._should_run_support_rag(
        needs_support_rag=plan.needs_support_rag,
        support_in_scope=True,
        route_mode="product_support_mixed",
    ) is True


def test_pipeline_payment_without_order_keeps_support_rag():
    _, plan = resolve_with_pipeline(
        "PAYMENT_CHARGED_ORDER_NOT_CREATED",
        "kartımdan para çekildi ama sipariş oluşmadı",
    )

    assert plan.next_step == "FETCH_CONTEXT"
    assert plan.needs_support_rag is True
    assert plan.data_sources == ["payment_db", "order_db"]


def test_pipeline_context_resolver_metadata_contains_full_plan():
    state = SimpleNamespace(last_product_id=22)
    pipeline, plan = resolve_with_pipeline(
        "PRODUCT_STOCK", "stokta mı?", state=state
    )

    metadata = pipeline._context_plan_metadata(plan)

    assert metadata["next_step"] == "FETCH_CONTEXT"
    assert metadata["resolved_entities"]["product_id"] == 22
    assert metadata["warnings"] == [USED_CONVERSATION_STATE]


def test_pipeline_infers_current_classifier_intent_without_finetune_fields():
    pipeline = SupportPipeline()
    current_classification = ClassificationResult(
        category="ODEME",
        subcategory="",
        priority="HIGH",
        expected_action="RAG_ANSWER",
        confidence=0.7,
    )

    resolver_input = pipeline._context_resolver_input(
        current_classification,
        "kartımdan para çekildi ama sipariş oluşmadı",
        canonical_query="kartımdan para çekildi ama sipariş oluşmadı",
        is_in_scope=True,
        conversation_state=None,
        frontend_context={},
        followup_reference={},
    )

    assert (
        resolver_input["classifier_output"]["intent"]
        == "PAYMENT_CHARGED_ORDER_NOT_CREATED"
    )


def test_pipeline_explicit_product_never_falls_back_to_old_product_state():
    state = SimpleNamespace(last_product_id=99)
    _, plan = resolve_with_pipeline(
        "PRODUCT_ATTRIBUTE", "çay bardağı kaç ml?", state=state
    )

    assert plan.resolved_entities.product_id is None
    assert plan.resolved_entities.product_name == "çay bardağı"
    assert plan.next_step == "FETCH_CONTEXT"
    assert USED_CONVERSATION_STATE not in plan.warnings


def test_pipeline_explicit_order_product_never_uses_old_order_state():
    state = SimpleNamespace(last_order_id=88)
    _, plan = resolve_with_pipeline(
        "ORDER_STATUS", "sandalye siparişim nerede?", state=state
    )

    assert plan.resolved_entities.order_id is None
    assert plan.resolved_entities.product_name == "sandalye"
    assert plan.next_step == "CLARIFY"
    assert USED_CONVERSATION_STATE not in plan.warnings
