import pytest

from backend.app.schemas.data_resolver import (
    DataResolutionStatus,
    EntityType,
    ResolutionNextStep,
)
from backend.app.services.data_resolver import (
    USED_CONVERSATION_STATE,
    DataResolver,
    InMemoryDataResolverAdapter,
    SqlAlchemyDataResolverAdapter,
    ResolverRecord,
)


def record(entity_type, record_id, value, *, owner_user_id=None):
    return ResolverRecord(
        entity_type=entity_type,
        record_id=record_id,
        display_label=value,
        lookup_value=value,
        owner_user_id=owner_user_id,
    )


def resolver(records):
    return DataResolver(InMemoryDataResolverAdapter(records))


def request(
    *,
    sources,
    entities=None,
    state=None,
    frontend=None,
    entity_references=None,
):
    return {
        "user_id": 1,
        "message": "test message",
        "context_plan": {
            "resolved_entities": entities or {},
            "data_sources": sources,
            "fields": [],
            "needs_support_rag": False,
            "support_doc_ids": [],
            "needs_clarification": False,
            "clarification_reason": None,
            "fallback_reason": None,
            "next_step": "FETCH_CONTEXT",
            "confidence": 1.0,
            "warnings": [],
        },
        "entity_references": entity_references or [],
        "conversation_state": state or {},
        "frontend_context": frontend or {},
    }


@pytest.mark.asyncio
async def test_product_exact_match_is_resolved():
    result = await resolver(
        [record(EntityType.PRODUCT, 15, "Çay Bardağı")]
    ).resolve(request(sources=["product_db"], entities={"product_name": "çay bardağı"}))

    assert result.status == DataResolutionStatus.RESOLVED
    assert result.resolved_entities.product_id == 15
    assert result.entity_results[0].match_type == "EXACT_NAME"
    assert result.next_step == ResolutionNextStep.FETCH_EVIDENCE


@pytest.mark.asyncio
async def test_product_no_match_never_selects_another_product():
    result = await resolver(
        [record(EntityType.PRODUCT, 99, "Kahve Kupası")]
    ).resolve(request(sources=["product_db"], entities={"product_name": "çay bardağı"}))

    assert result.status == DataResolutionStatus.NO_MATCH
    assert result.resolved_entities.product_id is None
    assert result.entity_results[0].resolved_id is None
    assert result.next_step == ResolutionNextStep.ASK_CLARIFICATION


@pytest.mark.asyncio
async def test_product_multiple_exact_matches_are_ambiguous():
    result = await resolver(
        [
            record(EntityType.PRODUCT, 1, "Çay Bardağı"),
            record(EntityType.PRODUCT, 2, "Çay Bardağı"),
        ]
    ).resolve(request(sources=["product_db"], entities={"product_name": "çay bardağı"}))

    assert result.status == DataResolutionStatus.AMBIGUOUS
    assert result.resolved_entities.product_id is None
    assert [item.record_id for item in result.entity_results[0].candidates] == [1, 2]
    assert result.next_step == ResolutionNextStep.ASK_CLARIFICATION


@pytest.mark.asyncio
async def test_explicit_product_name_does_not_use_last_product():
    result = await resolver(
        [
            record(EntityType.PRODUCT, 15, "Çay Bardağı"),
            record(EntityType.PRODUCT, 99, "Eski Ürün"),
        ]
    ).resolve(
        request(
            sources=["product_db"],
            entities={"product_name": "çay bardağı"},
            state={"last_product_id": 99},
        )
    )

    assert result.resolved_entities.product_id == 15
    assert USED_CONVERSATION_STATE not in result.warnings


@pytest.mark.asyncio
async def test_product_uses_last_product_only_without_explicit_entity():
    result = await resolver(
        [record(EntityType.PRODUCT, 99, "Önceki Ürün")]
    ).resolve(
        request(
            sources=["product_db"],
            entities={"product_id": 99},
            state={"last_product_id": 99},
        )
    )

    assert result.status == DataResolutionStatus.RESOLVED
    assert result.resolved_entities.product_id == 99
    assert USED_CONVERSATION_STATE in result.warnings


@pytest.mark.asyncio
async def test_order_number_exact_match_is_resolved_for_owner():
    result = await resolver(
        [record(EntityType.ORDER, 8, "DMO-1-008", owner_user_id=1)]
    ).resolve(request(sources=["order_db"], entities={"order_no": "dmo-1-008"}))

    assert result.status == DataResolutionStatus.RESOLVED
    assert result.resolved_entities.order_id == 8
    assert result.entity_results[0].match_type == "EXACT_ORDER_NO"


@pytest.mark.asyncio
async def test_explicit_order_number_does_not_use_last_order():
    result = await resolver(
        [
            record(EntityType.ORDER, 8, "DMO-1-008", owner_user_id=1),
            record(EntityType.ORDER, 99, "DMO-1-099", owner_user_id=1),
        ]
    ).resolve(
        request(
            sources=["order_db"],
            entities={"order_no": "DMO-1-008"},
            state={"last_order_id": 99},
        )
    )

    assert result.resolved_entities.order_id == 8
    assert USED_CONVERSATION_STATE not in result.warnings


@pytest.mark.asyncio
async def test_order_no_match_never_selects_recent_order():
    result = await resolver(
        [record(EntityType.ORDER, 99, "DMO-1-099", owner_user_id=1)]
    ).resolve(
        request(
            sources=["order_db"],
            entities={"order_no": "DMO-1-MISSING"},
            state={"last_order_id": 99},
        )
    )

    assert result.status == DataResolutionStatus.NO_MATCH
    assert result.resolved_entities.order_id is None
    assert USED_CONVERSATION_STATE not in result.warnings


@pytest.mark.asyncio
async def test_coupon_code_exact_match_is_resolved():
    result = await resolver(
        [record(EntityType.COUPON, 7, "KUPON10")]
    ).resolve(request(sources=["coupon_db"], entities={"coupon_code": "kupon10"}))

    assert result.status == DataResolutionStatus.RESOLVED
    assert result.resolved_entities.coupon_id == 7
    assert result.entity_results[0].match_type == "EXACT_COUPON_CODE"


@pytest.mark.asyncio
async def test_coupon_no_match_never_uses_another_coupon():
    result = await resolver(
        [record(EntityType.COUPON, 7, "ACTIVE-CART-COUPON")]
    ).resolve(request(sources=["coupon_db", "cart_db"], entities={"coupon_code": "MISSING"}))

    assert result.status == DataResolutionStatus.NO_MATCH
    assert result.resolved_entities.coupon_id is None
    assert result.entity_results[0].resolved_id is None


@pytest.mark.asyncio
async def test_frontend_current_product_is_used_without_explicit_product():
    result = await resolver(
        [record(EntityType.PRODUCT, 12, "Current Product")]
    ).resolve(
        request(
            sources=["product_db"],
            entities={"product_id": 12},
            frontend={"current_product_id": 12, "page_context": "product"},
        )
    )

    assert result.status == DataResolutionStatus.RESOLVED
    assert result.resolved_entities.product_id == 12
    assert result.entity_results[0].match_type == "FRONTEND_CONTEXT"


@pytest.mark.asyncio
async def test_low_confidence_fuzzy_match_requires_clarification():
    result = await resolver(
        [
            record(EntityType.PRODUCT, 1, "Çay Bardağı Seti"),
            record(EntityType.PRODUCT, 2, "Çay Bardağı Takımı"),
        ]
    ).resolve(request(sources=["product_db"], entities={"product_name": "çay bardağı"}))

    assert result.status == DataResolutionStatus.AMBIGUOUS
    assert result.resolved_entities.product_id is None
    assert result.next_step == ResolutionNextStep.ASK_CLARIFICATION


@pytest.mark.asyncio
async def test_multiple_explicit_products_require_clarification():
    result = await resolver(
        [
            record(EntityType.PRODUCT, 1, "Çay Bardağı"),
            record(EntityType.PRODUCT, 2, "Kahve Kupası"),
        ]
    ).resolve(
        request(
            sources=["product_db"],
            entity_references=[
                {"entity_type": "PRODUCT", "type": "NAME", "value": "çay bardağı"},
                {"entity_type": "PRODUCT", "type": "NAME", "value": "kahve kupası"},
            ],
        )
    )

    assert result.status == DataResolutionStatus.AMBIGUOUS
    assert result.resolved_entities.product_id is None
    assert result.next_step == ResolutionNextStep.ASK_CLARIFICATION


@pytest.mark.asyncio
async def test_other_users_order_is_not_returned_as_candidate():
    result = await resolver(
        [record(EntityType.ORDER, 22, "DMO-2-022", owner_user_id=2)]
    ).resolve(request(sources=["order_db"], entities={"order_no": "DMO-2-022"}))

    assert result.status == DataResolutionStatus.NO_MATCH
    assert result.entity_results[0].candidates == []
    assert result.resolved_entities.order_id is None


@pytest.mark.asyncio
async def test_fallback_context_plan_is_skipped_without_lookup():
    payload = request(sources=[], entities={})
    payload["context_plan"]["next_step"] = "FALLBACK"

    result = await resolver([]).resolve(payload)

    assert result.status == DataResolutionStatus.SKIP
    assert result.next_step == ResolutionNextStep.SKIP


def test_sqlalchemy_record_uses_entity_specific_fields():
    product = type(
        "DemoProductRow",
        (),
        {"id": 15, "name": "Çay Bardağı", "user_id": 1},
    )()

    record = SqlAlchemyDataResolverAdapter._record(EntityType.PRODUCT, product)

    assert record.record_id == 15
    assert record.display_label == "Çay Bardağı"
    assert record.lookup_value == "Çay Bardağı"
