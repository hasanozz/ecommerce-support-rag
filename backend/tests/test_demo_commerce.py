from decimal import Decimal

import pytest

from backend.app.services.demo_commerce import DemoCommerceService
from backend.app.services.pipeline import SupportPipeline


class Product:
    category = "MODA"


class Item:
    product = Product()


class Coupon:
    is_active = True
    status = "VALID"
    expires_at = None
    min_cart_total = Decimal("500")
    allowed_category = ""


def test_coupon_min_cart_total_not_met():
    valid, message = DemoCommerceService().validate_coupon(
        Coupon(), [Item()], Decimal("100")
    )

    assert valid is False
    assert message == "Minimum sepet tutarı yetersiz."


def test_coupon_category_mismatch():
    coupon = Coupon()
    coupon.min_cart_total = Decimal("0")
    coupon.allowed_category = "ELEKTRONIK"

    valid, message = DemoCommerceService().validate_coupon(
        coupon, [Item()], Decimal("1000")
    )

    assert valid is False
    assert message == "Kupon sepetteki ürün kategorileri için uygun değil."


def test_coupon_valid():
    coupon = Coupon()
    coupon.min_cart_total = Decimal("0")

    valid, message = DemoCommerceService().validate_coupon(
        coupon, [Item()], Decimal("1000")
    )

    assert valid is True
    assert message == "Kupon uygulandı."


def test_pipeline_resolves_ordinal_followup_from_previous_customer_context():
    reference = SupportPipeline()._resolve_followup_reference(
        "2. olan",
        {
            "category": "KARGO_TESLIMAT",
            "items": [
                "Sipariş DMO-1-001: kargo=Gecikti.",
                "Sipariş DMO-1-002: kargo=Yolda.",
                "Sipariş DMO-1-003: kargo=Hazırlanıyor.",
            ],
        },
    )

    assert reference == {
        "order_no": "DMO-1-002",
        "category": "KARGO_TESLIMAT",
        "is_followup": True,
    }


def test_pipeline_does_not_treat_duration_as_ordinal_followup():
    reference = SupportPipeline()._resolve_followup_reference(
        "2 gündür kargo hareketi yok",
        {
            "category": "KARGO_TESLIMAT",
            "items": [
                "Sipariş DMO-1-001: kargo=Gecikti.",
                "Sipariş DMO-1-002: kargo=Yolda.",
            ],
        },
    )

    assert reference == {}


def test_pipeline_reuses_single_order_for_contextual_followup():
    reference = SupportPipeline()._resolve_followup_reference(
        "peki ne zaman gelir",
        {
            "category": "KARGO_TESLIMAT",
            "items": ["Sipariş DMO-1-002: kargo=Yolda."],
            "text": "Sipariş DMO-1-002: kargo=Yolda.",
        },
    )

    assert reference == {
        "order_no": "DMO-1-002",
        "category": "KARGO_TESLIMAT",
        "is_followup": True,
    }


def test_pipeline_reuses_category_for_contextual_followup_without_single_order():
    reference = SupportPipeline()._resolve_followup_reference(
        "peki ne zaman gelir",
        {
            "category": "KARGO_TESLIMAT",
            "items": [
                "Sipariş DMO-1-001: kargo=Gecikti.",
                "Sipariş DMO-1-002: kargo=Yolda.",
            ],
            "text": "Sipariş DMO-1-001: kargo=Gecikti.\nSipariş DMO-1-002: kargo=Yolda.",
        },
    )

    assert reference == {"category": "KARGO_TESLIMAT", "is_followup": True}


def test_pipeline_does_not_reuse_context_for_unrelated_short_message():
    reference = SupportPipeline()._resolve_followup_reference(
        "merhaba",
        {
            "category": "KARGO_TESLIMAT",
            "items": ["Sipariş DMO-1-002: kargo=Yolda."],
            "text": "Sipariş DMO-1-002: kargo=Yolda.",
        },
    )

    assert reference == {}


@pytest.mark.asyncio
async def test_pipeline_fallback_uses_shipping_customer_context():
    answer = await SupportPipeline()._fallback_answer(
        session=None,
        grouped=[],
        customer_context={
            "category": "KARGO_TESLIMAT",
            "items": [
                "Sipariş DMO-1: kargo=Yolda; takip no=TRK1.",
                "Sipariş DMO-2: kargo=Gecikti; takip no=TRK2.",
            ],
            "text": "Sipariş DMO-1: kargo=Yolda; takip no=TRK1.\nSipariş DMO-2: kargo=Gecikti; takip no=TRK2.",
        },
    )

    assert "birden fazla demo sipariş" in answer
    assert "DMO-1" in answer
    assert "DMO-2" in answer
