from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

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
    import os

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from backend.app.config import get_settings
    from backend.app.models import User

    os.environ['SECRETS_FILE'] = r'C:\Users\hasanozz\Desktop\teknopark-ai\project_secrets\.env.local'
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as session:
        user = await session.scalar(select(User).order_by(User.id.asc()))
        service = ProductContextService()

        blender_ctx = await service.build(
            session,
            user,
            'GENEL_DESTEK',
            'blenderin özelliklerini anlatsana bana',
        )
        assert blender_ctx['route_mode'] == 'product_only'
        assert blender_ctx['product_match_reason'] == 'catalog_match'
        assert blender_ctx['primary_product']['name'] == 'Blender'
        assert 'Sırt Çantası' not in blender_ctx['text']
        assert 'Blender' in blender_ctx['text']

        headphone_ctx = await service.build(
            session,
            user,
            'GENEL_DESTEK',
            'Kablosuz Kulaklık hakkında bilgi verir misin?',
        )
        assert headphone_ctx['route_mode'] == 'product_only'
        assert headphone_ctx['primary_product']['name'] == 'Kablosuz Kulaklık'
        assert 'Sırt Çantası' not in headphone_ctx['text']

        support_ctx = await service.build(
            session,
            user,
            'ODEME',
            'Kartımdan para çekildi ama siparişim oluşmadı.',
        )
        assert support_ctx['route_mode'] == 'support_only'
        assert support_ctx['selected_product_ids'] == []
        assert support_ctx['text'] == ''

    await engine.dispose()
