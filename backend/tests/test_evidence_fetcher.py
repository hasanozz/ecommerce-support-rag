from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.schemas.evidence_fetcher import EvidencePurpose
from backend.app.services.evidence_fetcher import (
    EvidenceFetcher,
    EvidenceRecord,
    InMemoryEvidenceFetcherAdapter,
)


def context_plan(entities=None):
    return {
        "resolved_entities": entities or {},
        "data_sources": [],
        "fields": [],
        "needs_support_rag": False,
        "support_doc_ids": [],
        "needs_clarification": False,
        "clarification_reason": None,
        "fallback_reason": None,
        "next_step": "FETCH_CONTEXT",
        "confidence": 1.0,
        "warnings": [],
    }


def data_resolution(**resolved_entities):
    return {
        "status": "RESOLVED",
        "resolved_entities": resolved_entities,
        "entity_results": [],
        "missing_entities": [],
        "ambiguous_entities": [],
        "unfulfilled_contexts": [],
        "evidence_refs": [],
        "warnings": [],
        "next_step": "FETCH_EVIDENCE",
    }


def request(purpose, *, resolved=None, fields_hint=None, plan_entities=None):
    return {
        "user_id": 1,
        "context_plan": context_plan(plan_entities),
        "data_resolution": data_resolution(**(resolved or {})),
        "required_contexts": [
            {
                "purpose": purpose,
                "fields_hint": fields_hint or [],
            }
        ],
    }


def record(purpose, entity_type, entity_id, source, data, *, record_id=None):
    return EvidenceRecord(
        purpose=purpose,
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
        record_id=record_id or entity_id,
        data=data,
    )


@pytest.mark.asyncio
async def test_product_capacity_evidence_uses_resolved_product_only():
    evidence_record = record(
        EvidencePurpose.PRODUCT_CAPACITY,
        "PRODUCT",
        15,
        "PRODUCT_CATALOG",
        {
            "name": "Çay Bardağı",
            "capacity_ml": 120,
            "volume_ml": 120,
            "price": 99,
        },
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("PRODUCT_CAPACITY", resolved={"product_id": 15}))

    assert len(output.product_evidence) == 1
    assert output.product_evidence[0].entity_id == 15
    assert output.product_evidence[0].data == {
        "name": "Çay Bardağı",
        "capacity_ml": 120,
        "volume_ml": 120,
    }


@pytest.mark.asyncio
async def test_product_capacity_without_id_produces_missing_evidence():
    output = await EvidenceFetcher(InMemoryEvidenceFetcherAdapter()).fetch(
        request("PRODUCT_CAPACITY")
    )

    assert output.product_evidence == []
    assert output.missing_evidence[0].reason == "PRODUCT_ID_MISSING"


@pytest.mark.asyncio
async def test_product_price_returns_only_price_fields():
    evidence_record = record(
        EvidencePurpose.PRODUCT_PRICE,
        "PRODUCT",
        3,
        "PRODUCT_CATALOG",
        {
            "name": "Kupa",
            "price": 120,
            "discounted_price": 99,
            "currency": "TRY",
            "stock": 20,
        },
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("PRODUCT_PRICE", resolved={"product_id": 3}))

    assert output.product_evidence[0].data == {
        "price": 120,
        "discounted_price": 99,
        "currency": "TRY",
    }


@pytest.mark.asyncio
async def test_product_stock_returns_only_stock_fields():
    evidence_record = record(
        EvidencePurpose.PRODUCT_STOCK,
        "PRODUCT",
        4,
        "PRODUCT_CATALOG",
        {"stock": 8, "availability": "IN_STOCK", "price": 50},
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("PRODUCT_STOCK", resolved={"product_id": 4}))

    assert output.product_evidence[0].data == {
        "stock": 8,
        "availability": "IN_STOCK",
    }


@pytest.mark.asyncio
async def test_order_status_uses_exact_resolved_order():
    evidence_record = record(
        EvidencePurpose.ORDER_STATUS,
        "ORDER",
        20,
        "ORDER_LEDGER",
        {
            "order_no": "DMO-1-020",
            "order_status": "SHIPPED",
            "shipping_status": "IN_TRANSIT",
            "payment_status": "SUCCESS",
        },
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("ORDER_STATUS", resolved={"order_id": 20}))

    assert output.order_evidence[0].entity_id == 20


@pytest.mark.asyncio
async def test_order_status_without_id_does_not_fallback():
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter(
            [
                record(
                    EvidencePurpose.ORDER_STATUS,
                    "ORDER",
                    99,
                    "ORDER_LEDGER",
                    {"order_status": "DELIVERED"},
                )
            ]
        )
    ).fetch(request("ORDER_STATUS"))

    assert output.order_evidence == []
    assert output.missing_evidence[0].reason == "ORDER_ID_MISSING"


@pytest.mark.asyncio
async def test_coupon_status_uses_exact_resolved_coupon():
    evidence_record = record(
        EvidencePurpose.COUPON_STATUS,
        "COUPON",
        7,
        "COUPON_CATALOG",
        {"code": "KUPON10", "status": "VALID", "is_active": True},
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("COUPON_STATUS", resolved={"coupon_id": 7}))

    assert output.coupon_evidence[0].entity_id == 7


@pytest.mark.asyncio
async def test_coupon_status_without_id_does_not_use_active_coupon():
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter(
            [
                record(
                    EvidencePurpose.COUPON_STATUS,
                    "COUPON",
                    88,
                    "COUPON_CATALOG",
                    {"code": "ACTIVE", "status": "VALID"},
                )
            ]
        )
    ).fetch(request("COUPON_STATUS"))

    assert output.coupon_evidence == []
    assert output.missing_evidence[0].reason == "COUPON_ID_MISSING"


@pytest.mark.asyncio
async def test_payment_status_uses_exact_resolved_payment():
    evidence_record = record(
        EvidencePurpose.PAYMENT_STATUS,
        "PAYMENT",
        30,
        "PAYMENT_LEDGER",
        {"status": "SUCCESS", "amount": 250, "provider_reference": "PAY-30"},
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("PAYMENT_STATUS", resolved={"payment_id": 30}))

    assert output.payment_evidence[0].entity_id == 30


@pytest.mark.asyncio
async def test_payment_status_without_id_produces_missing_evidence():
    output = await EvidenceFetcher(InMemoryEvidenceFetcherAdapter()).fetch(
        request("PAYMENT_STATUS")
    )

    assert output.payment_evidence == []
    assert output.missing_evidence[0].reason == "PAYMENT_ID_MISSING"


@pytest.mark.asyncio
async def test_unknown_purpose_produces_warning_without_fetching():
    output = await EvidenceFetcher(InMemoryEvidenceFetcherAdapter()).fetch(
        request("UNKNOWN_PURPOSE")
    )

    assert output.warnings == ["UNKNOWN_PURPOSE:UNKNOWN_PURPOSE"]
    assert output.missing_evidence == []


@pytest.mark.asyncio
async def test_evidence_contains_provenance():
    evidence_record = record(
        EvidencePurpose.PRODUCT_STOCK,
        "PRODUCT",
        5,
        "PRODUCT_CATALOG",
        {"stock": 2, "availability": "LOW_STOCK"},
        record_id=500,
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("PRODUCT_STOCK", resolved={"product_id": 5}))

    assert output.product_evidence[0].provenance.model_dump() == {
        "source": "PRODUCT_CATALOG",
        "record_id": 500,
    }


@pytest.mark.asyncio
async def test_fields_hint_can_only_narrow_allowed_purpose_fields():
    evidence_record = record(
        EvidencePurpose.PRODUCT_CAPACITY,
        "PRODUCT",
        6,
        "PRODUCT_CATALOG",
        {"name": "Bardak", "capacity_ml": 100, "volume_ml": 100, "secret": "x"},
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(
        request(
            "PRODUCT_CAPACITY",
            resolved={"product_id": 6},
            fields_hint=["capacity_ml", "secret"],
        )
    )

    assert output.product_evidence[0].data == {"capacity_ml": 100}


@pytest.mark.asyncio
async def test_fetcher_does_not_mutate_adapter_record_data():
    data = {"stock": 3, "availability": "IN_STOCK", "internal": {"x": 1}}
    original = deepcopy(data)
    evidence_record = record(
        EvidencePurpose.PRODUCT_STOCK,
        "PRODUCT",
        9,
        "PRODUCT_CATALOG",
        data,
    )

    await EvidenceFetcher(InMemoryEvidenceFetcherAdapter([evidence_record])).fetch(
        request("PRODUCT_STOCK", resolved={"product_id": 9})
    )

    assert data == original


@pytest.mark.asyncio
async def test_other_users_evidence_is_not_returned():
    evidence_record = EvidenceRecord(
        purpose=EvidencePurpose.ORDER_STATUS,
        entity_type="ORDER",
        entity_id=44,
        source="ORDER_LEDGER",
        record_id=44,
        data={"order_status": "SHIPPED"},
        owner_user_id=2,
    )
    output = await EvidenceFetcher(
        InMemoryEvidenceFetcherAdapter([evidence_record])
    ).fetch(request("ORDER_STATUS", resolved={"order_id": 44}))

    assert output.order_evidence == []
    assert output.missing_evidence[0].reason == "EVIDENCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_product_name_never_triggers_entity_resolution():
    adapter = SimpleNamespace(fetch=AsyncMock())

    output = await EvidenceFetcher(adapter).fetch(
        request(
            "PRODUCT_CAPACITY",
            plan_entities={"product_name": "Çay Bardağı"},
        )
    )

    adapter.fetch.assert_not_awaited()
    assert output.product_evidence == []
    assert output.missing_evidence[0].reason == "PRODUCT_ID_MISSING"


@pytest.mark.asyncio
async def test_order_number_never_triggers_entity_resolution():
    adapter = SimpleNamespace(fetch=AsyncMock())

    output = await EvidenceFetcher(adapter).fetch(
        request(
            "ORDER_STATUS",
            plan_entities={"order_no": "DMO-1-001"},
        )
    )

    adapter.fetch.assert_not_awaited()
    assert output.order_evidence == []
    assert output.missing_evidence[0].reason == "ORDER_ID_MISSING"


@pytest.mark.asyncio
async def test_coupon_code_never_triggers_entity_resolution():
    adapter = SimpleNamespace(fetch=AsyncMock())

    output = await EvidenceFetcher(adapter).fetch(
        request(
            "COUPON_STATUS",
            plan_entities={"coupon_code": "KUPON10"},
        )
    )

    adapter.fetch.assert_not_awaited()
    assert output.coupon_evidence == []
    assert output.missing_evidence[0].reason == "COUPON_ID_MISSING"


@pytest.mark.asyncio
async def test_fetcher_uses_only_authoritative_resolved_entity_id():
    evidence_record = record(
        EvidencePurpose.PRODUCT_STOCK,
        "PRODUCT",
        77,
        "PRODUCT_CATALOG",
        {"stock": 1, "availability": "LOW_STOCK"},
    )
    adapter = SimpleNamespace(fetch=AsyncMock(return_value=evidence_record))

    output = await EvidenceFetcher(adapter).fetch(
        request(
            "PRODUCT_STOCK",
            resolved={"product_id": 77},
            plan_entities={"product_id": 99, "product_name": "Başka Ürün"},
        )
    )

    adapter.fetch.assert_awaited_once_with(EvidencePurpose.PRODUCT_STOCK, 77, 1)
    assert output.product_evidence[0].entity_id == 77
