from backend.app.services.context_resolver import (
    USED_CONVERSATION_STATE,
    ContextResolver,
)


def resolver_input(
    message: str,
    intent: str,
    *,
    requested_info: str | None = None,
    entities: dict | None = None,
    conversation_state: dict | None = None,
    doc_id: str | None = None,
) -> dict:
    return {
        "message": message,
        "classifier_output": {
            "domain": "PRODUCT",
            "intent": intent,
            "category": None,
            "subcategory": None,
            "doc_id": doc_id,
            "entities": entities or {},
            "requested_info": requested_info,
        },
        "conversation_state": conversation_state or {},
    }


def test_product_capacity_plans_only_product_fields_without_rag():
    result = ContextResolver().resolve(
        resolver_input(
            "çay bardağı kaç ml?",
            "PRODUCT_ATTRIBUTE",
            requested_info="capacity",
            entities={"product_name": "çay bardağı"},
        )
    )

    assert result.data_sources == ["product_db"]
    assert result.fields == ["capacity_ml", "volume_ml", "description"]
    assert result.needs_support_rag is False
    assert result.resolved_entities.product_name == "çay bardağı"
    assert result.needs_clarification is False
    assert result.next_step == "FETCH_CONTEXT"


def test_product_stock_uses_last_product():
    result = ContextResolver().resolve(
        resolver_input(
            "stokta mı?",
            "PRODUCT_STOCK",
            conversation_state={"last_product_id": 41},
        )
    )

    assert result.data_sources == ["product_db"]
    assert result.fields == ["stock", "availability"]
    assert result.resolved_entities.product_id == 41
    assert result.needs_support_rag is False


def test_product_reviews_uses_last_product_without_clarification():
    result = ContextResolver().resolve(
        resolver_input(
            "yorumları nasıl?",
            "PRODUCT_REVIEWS",
            conversation_state={"last_product_id": 8},
        )
    )

    assert "review_db" in result.data_sources
    assert result.resolved_entities.product_id == 8
    assert result.needs_clarification is False


def test_product_reviews_without_product_context_requires_clarification():
    result = ContextResolver().resolve(
        resolver_input("yorumları nasıl?", "PRODUCT_REVIEWS")
    )

    assert result.needs_clarification is True
    assert result.clarification_reason == "PRODUCT_CONTEXT_REQUIRED"
    assert result.next_step == "CLARIFY"


def test_product_return_eligibility_needs_product_and_support_policy():
    result = ContextResolver().resolve(
        resolver_input(
            "bu ürün iade olur mu?",
            "PRODUCT_RETURN_ELIGIBILITY",
            conversation_state={"last_product_id": 12},
            doc_id="IADE_POLICY_001",
        )
    )

    assert result.data_sources == ["product_db"]
    assert result.needs_support_rag is True
    assert result.support_doc_ids == ["IADE_POLICY_001"]


def test_product_name_does_not_fallback_to_an_unrelated_order():
    result = ContextResolver().resolve(
        resolver_input(
            "sandalye siparişim nerede?",
            "ORDER_STATUS",
            entities={"product_name": "sandalye"},
        )
    )

    assert result.resolved_entities.order_id is None
    assert result.needs_clarification is True
    assert result.clarification_reason == "ORDER_REFERENCE_COULD_NOT_BE_RESOLVED"


def test_order_cancel_uses_last_order_and_needs_policy():
    result = ContextResolver().resolve(
        resolver_input(
            "siparişimi iptal etmek istiyorum",
            "ORDER_CANCEL",
            conversation_state={"last_order_id": 77},
        )
    )

    assert result.data_sources == ["order_db"]
    assert result.resolved_entities.order_id == 77
    assert result.needs_support_rag is True


def test_payment_without_order_plans_payment_order_and_support_context():
    result = ContextResolver().resolve(
        resolver_input(
            "kartımdan para çekildi ama sipariş oluşmadı",
            "PAYMENT_CHARGED_ORDER_NOT_CREATED",
        )
    )

    assert result.data_sources == ["payment_db", "order_db"]
    assert result.needs_support_rag is True
    assert result.needs_clarification is False


def test_out_of_domain_returns_fallback_without_context_sources():
    result = ContextResolver().resolve(
        resolver_input("yarın hava nasıl?", "OUT_OF_DOMAIN")
    )

    assert result.next_step == "FALLBACK"
    assert result.data_sources == []
    assert result.needs_support_rag is False
    assert result.fallback_reason == "OUT_OF_DOMAIN"


def test_unsafe_returns_fallback_without_context_sources():
    result = ContextResolver().resolve(resolver_input("zararlı istek", "UNSAFE"))

    assert result.next_step == "FALLBACK"
    assert result.data_sources == []
    assert result.fallback_reason == "UNSAFE_REQUEST"


def test_coupon_invalid_plans_coupon_cart_and_support_context():
    result = ContextResolver().resolve(
        resolver_input(
            "KUPON10 neden çalışmıyor?",
            "COUPON_INVALID",
            entities={"coupon_code": "KUPON10"},
        )
    )

    assert result.data_sources == ["coupon_db", "cart_db"]
    assert result.resolved_entities.coupon_code == "KUPON10"
    assert result.needs_support_rag is True


def test_followup_records_conversation_state_usage_warning():
    result = ContextResolver().resolve(
        resolver_input(
            "kaç ml?",
            "PRODUCT_ATTRIBUTE",
            requested_info="capacity",
            conversation_state={"last_product_id": 5},
        )
    )

    assert result.resolved_entities.product_id == 5
    assert USED_CONVERSATION_STATE in result.warnings


def test_explicit_order_reference_is_delegated_without_using_last_order():
    result = ContextResolver().resolve(
        resolver_input(
            "DMO-BILINMEYEN siparişim nerede?",
            "ORDER_STATUS",
            entities={"order_no": "DMO-BILINMEYEN"},
            conversation_state={"last_order_id": 99},
        )
    )

    assert result.resolved_entities.order_id is None
    assert result.resolved_entities.order_no == "DMO-BILINMEYEN"
    assert result.needs_clarification is False
    assert result.next_step == "FETCH_CONTEXT"
    assert USED_CONVERSATION_STATE not in result.warnings
