from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from backend.app.schemas.conversation import MessageCreate
from backend.app.schemas.demo_commerce import DemoProductReviewUpsert
from backend.app.services.demo_seed import (
    build_product_ai_context,
    build_product_search_text,
    money,
)
from backend.app.services.product_context import ProductContextService


DEMO_DATA = Path("data/demo")


def load_json(name: str):
    return json.loads((DEMO_DATA / name).read_text(encoding="utf-8"))


def test_demo_product_seed_has_unique_skus_and_decimal_prices():
    products = load_json("products.json")
    skus = [item["sku"] for item in products]

    assert len(products) >= 10
    assert len(skus) == len(set(skus))
    assert all(isinstance(item["price"], str) for item in products)
    assert money(products[0]["price"]) == Decimal(products[0]["price"]).quantize(
        Decimal("0.01")
    )


def test_demo_product_seed_references_are_valid():
    products = load_json("products.json")
    product_skus = {item["sku"] for item in products}
    reviews = load_json("product_reviews.json")
    scenario = load_json("demo_scenarios.json")

    assert {item["sku"] for item in reviews}.issubset(product_skus)
    assert {
        item["sku"] for item in scenario.get("cart", {}).get("items", [])
    }.issubset(product_skus)
    order_skus = {
        order_item["product_sku"]
        for order in scenario.get("orders", [])
        for order_item in order.get("items", [])
    }
    assert order_skus.issubset(product_skus)
    assert {item["sku"] for item in scenario.get("favorites", [])}.issubset(
        product_skus
    )
    assert {item["sku"] for item in scenario.get("reviews", [])}.issubset(product_skus)
    assert len(scenario.get("returns", [])) >= 2
    assert "returns" in scenario
    assert "saved_cards" in scenario
    assert "wallet" in scenario
    assert "security" in scenario
    assert any("items" in item for item in scenario.get("orders", []))


def test_review_rating_contract_allows_null_zero_and_five():
    assert DemoProductReviewUpsert(rating=None).rating is None
    assert DemoProductReviewUpsert(rating=0).rating == 0
    assert DemoProductReviewUpsert(rating=5).rating == 5

    with pytest.raises(ValidationError):
        DemoProductReviewUpsert(rating=-1)
    with pytest.raises(ValidationError):
        DemoProductReviewUpsert(rating=6)


def test_message_create_accepts_optional_frontend_context():
    payload = MessageCreate(
        message="Bu ürün iade edilebilir mi?",
        current_product_id=12,
        current_order_id=3,
        current_cart_id=1,
        current_return_id=2,
        current_payment_id=4,
        page_context="product",
    )

    assert payload.current_product_id == 12
    assert payload.page_context == "product"


def test_product_search_and_ai_context_include_attributes_without_float_prices():
    product = load_json("products.json")[0]

    search_text = build_product_search_text(product)
    ai_context = build_product_ai_context(product)

    assert product["sku"] in search_text
    assert product["name"] in search_text
    assert "gramaj" in search_text
    assert "500g" in search_text
    assert product["price"] in ai_context
    assert "İade edilebilir" in ai_context


def test_product_context_routing_detects_product_and_return_flows():
    service = ProductContextService()

    assert service._detect_route_mode("GENEL_DESTEK", "Siyah çay kaç gram?") == "product_only"
    assert service._detect_route_mode("GENEL_DESTEK", "Sepetimdeki ürüne kupon olur mu?") == "cart_coupon_mixed"
    assert service._detect_route_mode("GENEL_DESTEK", "İade kodumu nereden alabilirim?") == "return_refund_mixed"
    assert service._looks_like_followup("bunu favoriye ekle") is True
    assert service._looks_like_followup("İade kodumu nereden alabilirim?") is False


@pytest.mark.asyncio
async def test_product_context_prefers_explicit_catalog_matches_and_ignores_support_queries():
    service = ProductContextService()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    user = SimpleNamespace(id=1)
    blender = SimpleNamespace(
        id=11,
        sku="BLENDER-001",
        name="Blender",
        brand="DemoHome",
        category="HOME_KITCHEN",
        subcategory="BLENDER",
        price=Decimal("1299.90"),
        currency="TRY",
        stock=12,
        returnable=True,
        warranty_months=24,
        description="Günlük kullanım için güçlü blender.",
        ai_context="1000 W motor gücü ve cam hazne sunar.",
        attributes={"guc_watt": "1000", "hazne_litre": "1.5", "mikrofon": False},
        tags=["mutfak", "blender"],
    )
    headphone = SimpleNamespace(
        id=12,
        sku="HEADPHONE-001",
        name="Kablosuz Kulaklık",
        brand="DemoAudio",
        category="ELECTRONICS",
        subcategory="HEADPHONE",
        price=Decimal("899.90"),
        currency="TRY",
        stock=8,
        returnable=True,
        warranty_months=12,
        description="Günlük kullanım için kablosuz kulaklık.",
        ai_context="Uzun pil ömrü ve mikrofon desteği sunar.",
        attributes={"pil_suresi_saat": "20", "mikrofon": True},
        tags=["ses", "kulaklık"],
    )

    service._selected_products = AsyncMock(side_effect=[[blender], [headphone]])
    service._product_stats = AsyncMock(return_value={11: {}, 12: {}})

    blender_ctx = await service.build(
        session,
        user,
        "GENEL_DESTEK",
        "blenderin özelliklerini anlatsana bana",
    )
    assert blender_ctx["route_mode"] == "product_only"
    assert blender_ctx["product_match_reason"] == "catalog_match"
    assert blender_ctx["primary_product"]["name"] == "Blender"
    assert "Sırt Çantası" not in blender_ctx["text"]
    assert "Blender" in blender_ctx["text"]

    headphone_ctx = await service.build(
        session,
        user,
        "GENEL_DESTEK",
        "Kablosuz Kulaklık hakkında bilgi verir misin?",
    )
    assert headphone_ctx["route_mode"] == "product_only"
    assert headphone_ctx["primary_product"]["name"] == "Kablosuz Kulaklık"
    assert "Sırt Çantası" not in headphone_ctx["text"]

    support_ctx = await service.build(
        session,
        user,
        "ODEME",
        "Kartımdan para çekildi ama siparişim oluşmadı.",
    )
    assert support_ctx["route_mode"] == "payment_account_mixed"
    assert support_ctx["selected_product_ids"] == []
    assert "Sırt Çantası" not in support_ctx["text"]
