from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.services.demo_commerce import CustomerContextService, DemoCommerceService
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


def fake_order(order_no, order_status, shipping_status, payment_status="SUCCESS"):
    return SimpleNamespace(
        order_no=order_no,
        order_status=order_status,
        shipping_status=shipping_status,
        payment_status=payment_status,
        shipment=None,
        items=[],
        admin_note="",
    )


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


def test_pipeline_does_not_treat_nereden_as_followup():
    reference = SupportPipeline()._resolve_followup_reference(
        "İade kodumu nereden alabilirim?",
        {
            "category": "KARGO_TESLIMAT",
            "items": ["Sipariş DMO-1-002: kargo=Yolda."],
            "text": "Sipariş DMO-1-002: kargo=Yolda.",
        },
    )

    assert reference == {}


def test_customer_context_detects_return_code_as_iade_intent():
    service = CustomerContextService()

    assert service._detect_intent("IADE", "İade kodumu nereden alabilirim?") == "return_code"


def test_customer_context_selects_delivered_order_for_not_received_intent():
    service = CustomerContextService()
    delivered = fake_order("DMO-1-003", "DELIVERED", "DELIVERED")
    in_transit = fake_order("DMO-1-002", "SHIPPED", "IN_TRANSIT")

    selected = service._selected_orders_for_intent(
        [in_transit, delivered], "KARGO_TESLIMAT", "delivered_not_received"
    )

    assert selected == [delivered]


def test_customer_context_marks_shipped_order_cancel_as_not_cancelable():
    service = CustomerContextService()
    order = fake_order("DMO-1-002", "SHIPPED", "IN_TRANSIT")

    decision = service._cancel_decision(order)

    assert "iptal edilemez" in decision
    assert "iade" in decision


def test_customer_context_marks_processing_order_cancel_as_possible():
    service = CustomerContextService()
    order = fake_order("DMO-1-001", "PROCESSING", "PREPARING")

    decision = service._cancel_decision(order)

    assert "iptale uygun olabilir" in decision


def test_customer_context_detects_coupon_and_payment_intents():
    service = CustomerContextService()

    assert service._detect_intent("KAMPANYA_PUAN", "Kupon kodum çalışmıyor") == "coupon_issue"
    assert (
        service._detect_intent("ODEME", "Kartımdan para çekildi ama siparişim oluşmadı")
        == "payment_without_order"
    )


@pytest.mark.asyncio
async def test_pipeline_fallback_uses_decision_hint_without_raw_listing():
    answer = await SupportPipeline()._fallback_answer(
        session=None,
        grouped=[],
        customer_context={
            "category": "KARGO_TESLIMAT",
            "intent": "shipped_order_cancel",
            "context_type": "intent",
            "items": [
                "Sipariş DMO-1: kargo=Yolda; takip no=TRK1; karar=Bu sipariş iptal edilemez, teslim sonrası iade önerilir.",
            ],
            "text": "Sipariş DMO-1: kargo=Yolda; takip no=TRK1; karar=Bu sipariş iptal edilemez, teslim sonrası iade önerilir.",
            "decision_hints": [
                "DMO-1: Bu sipariş iptal edilemez, teslim sonrası iade önerilir."
            ],
        },
    )

    assert "Durumunuz:" not in answer
    assert "Yanıt:" not in answer
    assert "Ne yapabilirsiniz?" not in answer
    assert "iptal edilemez" in answer
    assert "DMO-1" in answer
    assert "birden fazla demo sipariş" not in answer
    assert "Hesabınızdaki demo işlem bilgileri" not in answer


@pytest.mark.asyncio
async def test_pipeline_fallback_asks_clarification_for_unclear_customer_context():
    answer = await SupportPipeline()._fallback_answer(
        session=None,
        grouped=[],
        customer_context={
            "category": "SIPARIS",
            "context_type": "clarification_needed",
            "items": [],
            "text": "",
            "decision_hints": [],
        },
    )

    assert "net bir demo işlem seçemedim" in answer
    assert "sipariş, ödeme, iade veya kupon" in answer


@pytest.mark.asyncio
async def test_pipeline_product_fallback_does_not_expose_raw_context_fields():
    answer = await SupportPipeline()._fallback_answer(
        session=None,
        grouped=[],
        customer_context={},
        product_context={
            "items": [
                "Blender (BLENDER-001); kategori bilgisi=home_kitchen/blender; "
                "marka=DemoHome; fiyat=1299.90 TRY; stok=12; "
                "açıklama=Günlük kullanım için güçlü blender.; "
                "detay=1000 W motor gücü ve cam hazne sunar.; "
                "iade edilebilir=evet; garanti=24 ay; "
                "özellikler=motor gücü: 1000 W, hazne kapasitesi: 1.5 L, mikrofon: yok; "
                "yorum özeti=5/5: Sessiz ve güçlü"
            ],
            "decision_hints": [
                "Ürünün teknik özellikleri ve iade/garanti notu birlikte değerlendirilmelidir."
            ],
        },
    )

    assert "Blender" in answer
    assert "1000 W" in answer
    assert "hazne kapasitesi" in answer
    assert "ai_context" not in answer
    assert "kategori=" not in answer
    assert "guc_watt" not in answer
    assert "True" not in answer
    assert "False" not in answer
    assert "Durumunuz:" not in answer
    assert "Ne yapabilirsiniz?" not in answer


@pytest.mark.asyncio
async def test_pipeline_payment_fallback_does_not_expose_raw_context_fields():
    answer = await SupportPipeline()._fallback_answer(
        session=None,
        grouped=[],
        customer_context={
            "items": [
                "Ödeme kaydı PAY-NOORDER: durum=Ödeme alındı ama sipariş oluşmadı; "
                "tutar=899.90; bağlantı=siparişe bağlı değil; açıklama=Karttan çekim var."
            ],
            "decision_hints": [
                "Siparişe bağlı olmayan başarılı/çekilmiş ödeme var; HIGH öncelikli destek kaydı önerilir."
            ],
        },
    )

    assert "PAY-NOORDER" in answer
    assert "siparişe bağlı görünmüyor" in answer
    assert "yüksek öncelikli" in answer.lower() or "HIGH" in answer
    assert "durum=" not in answer
    assert "tutar=" not in answer
    assert "bağlantı=" not in answer
    assert "Durumunuz:" not in answer
