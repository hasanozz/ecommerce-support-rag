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
        search_text="Blender mutfak küçük ev aleti",
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
        search_text="Kablosuz kulaklık bluetooth mikrofon",
        ai_context="Uzun pil ömrü ve mikrofon desteği sunar.",
        attributes={"pil_suresi_saat": "20", "mikrofon": True},
        tags=["ses", "kulaklık"],
    )
    backpack = SimpleNamespace(
        id=13,
        sku="BAGS-BACKPACK-001",
        name="Sırt Çantası",
        brand="DemoBag",
        category="bags",
        subcategory="backpack",
        price=Decimal("599.90"),
        currency="TRY",
        stock=30,
        returnable=True,
        warranty_months=12,
        description="Laptop bölmeli sırt çantası.",
        search_text="Sırt çantası laptop ofis",
        ai_context="Laptop bölmesi ve suya dayanıklı kumaş sunar.",
        attributes={"laptop_bolmesi": True, "suya_dayanikli": True},
        tags=["sirt_cantasi", "laptop", "ofis"],
    )

    service._product_stats = AsyncMock(return_value={11: {}, 12: {}})
    session.scalars = AsyncMock(
        return_value=SimpleNamespace(all=lambda: [backpack, blender, headphone])
    )

    blender_ctx = await service.build(
        session,
        user,
        "GENEL_DESTEK",
        "blenderin özelliklerini anlatsana bana",
    )
    assert blender_ctx["route_mode"] == "product_only"
    assert blender_ctx["product_match_reason"] == "explicit_catalog_match"
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

    support_session = AsyncMock()
    support_session.scalar = AsyncMock(return_value=None)
    support_session.scalars = AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    support_ctx = await service.build(
        support_session,
        user,
        "ODEME",
        "Kartımdan para çekildi ama siparişim oluşmadı.",
    )
    assert support_ctx["route_mode"] == "payment_account_mixed"
    assert support_ctx["selected_product_ids"] == []
    assert "Sırt Çantası" not in support_ctx["text"]


@pytest.mark.asyncio
async def test_product_context_does_not_let_state_or_page_override_explicit_product_name():
    service = ProductContextService()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    user = SimpleNamespace(id=1)
    backpack = SimpleNamespace(
        id=13,
        sku="BAGS-BACKPACK-001",
        name="Sırt Çantası",
        brand="DemoBag",
        category="bags",
        subcategory="backpack",
        price=Decimal("599.90"),
        currency="TRY",
        stock=30,
        returnable=True,
        warranty_months=12,
        description="Laptop bölmeli sırt çantası.",
        search_text="Sırt çantası laptop ofis",
        ai_context="Laptop bölmesi ve suya dayanıklı kumaş sunar.",
        attributes={"laptop_bolmesi": True},
        tags=["sirt_cantasi", "laptop"],
    )
    filter_coffee = SimpleNamespace(
        id=21,
        sku="COFFEE-FILTRE-250",
        name="Filtre Kahve 250g",
        brand="Demo Kahve",
        category="coffee_equipment",
        subcategory="coffee",
        price=Decimal("169.90"),
        currency="TRY",
        stock=60,
        returnable=True,
        warranty_months=None,
        description="Filtre kahve makineleri ve dripper için orta öğütülmüş kahve.",
        search_text="Filtre Kahve 250g gramaj orta öğütüm",
        ai_context="250g orta öğütülmüş filtre kahve.",
        attributes={"gramaj": "250g", "ogutum": "orta"},
        tags=["filtre_kahve", "kahve"],
    )
    coffee_machine = SimpleNamespace(
        id=22,
        sku="COFFEE-MACHINE-FILTER-001",
        name="Filtre Kahve Makinesi",
        brand="DemoTech",
        category="electronics",
        subcategory="coffee_machine",
        price=Decimal("2199.90"),
        currency="TRY",
        stock=8,
        returnable=True,
        warranty_months=24,
        description="Zamanlayıcılı cam sürahili filtre kahve makinesi.",
        search_text="Filtre Kahve Makinesi elektronik",
        ai_context="900 W filtre kahve makinesi.",
        attributes={"guc_watt": 900},
        tags=["filtre_kahve", "kahve_makinesi"],
    )
    session.scalars = AsyncMock(
        return_value=SimpleNamespace(all=lambda: [backpack, filter_coffee, coffee_machine])
    )
    service._product_stats = AsyncMock(return_value={21: {}})

    ctx = await service.build(
        session,
        user,
        "GENEL_DESTEK",
        "Filtre Kahve 250g hakkında bilgi verir misin?",
        frontend_context={"current_product_id": 13, "page_context": "product"},
    )

    assert ctx["product_match_reason"] == "explicit_catalog_match"
    assert ctx["primary_product"]["name"] == "Filtre Kahve 250g"
    assert ctx["selected_product_ids"] == [21]
    assert "Sırt Çantası" not in ctx["text"]


@pytest.mark.asyncio
async def test_product_context_asks_clarification_for_unknown_or_ambiguous_products():
    service = ProductContextService()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    user = SimpleNamespace(id=1)
    filter_coffee = SimpleNamespace(
        id=21,
        sku="COFFEE-FILTRE-250",
        name="Filtre Kahve 250g",
        brand="Demo Kahve",
        category="coffee_equipment",
        subcategory="coffee",
        price=Decimal("169.90"),
        currency="TRY",
        stock=60,
        returnable=True,
        warranty_months=None,
        description="Filtre kahve.",
        search_text="Filtre Kahve 250g",
        ai_context="250g filtre kahve.",
        attributes={"gramaj": "250g"},
        tags=["filtre_kahve", "kahve"],
    )
    coffee_machine = SimpleNamespace(
        id=22,
        sku="COFFEE-MACHINE-FILTER-001",
        name="Filtre Kahve Makinesi",
        brand="DemoTech",
        category="electronics",
        subcategory="coffee_machine",
        price=Decimal("2199.90"),
        currency="TRY",
        stock=8,
        returnable=True,
        warranty_months=24,
        description="Filtre kahve makinesi.",
        search_text="Filtre Kahve Makinesi",
        ai_context="Kahve makinesi.",
        attributes={"guc_watt": 900},
        tags=["filtre_kahve", "kahve_makinesi"],
    )
    session.scalars = AsyncMock(
        return_value=SimpleNamespace(all=lambda: [filter_coffee, coffee_machine])
    )
    service._product_stats = AsyncMock(return_value={})

    ambiguous = await service.build(
        session, user, "GENEL_DESTEK", "Filtre kahve hakkında bilgi verir misin?"
    )
    assert ambiguous["selected_product_ids"] == []
    assert ambiguous["product_match_reason"] == "ambiguous_weak_match"
    assert {item["name"] for item in ambiguous["top_candidates"]} == {
        "Filtre Kahve 250g",
        "Filtre Kahve Makinesi",
    }

    unknown = await service.build(
        session, user, "GENEL_DESTEK", "xyz ürün hakkında bilgi ver"
    )
    assert unknown["selected_product_ids"] == []
    assert unknown["product_match_reason"] == "no_catalog_match"
