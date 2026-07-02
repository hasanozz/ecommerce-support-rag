from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


STATUS_LABELS = {
    "PROCESSING": "İşleniyor",
    "PREPARING": "Hazırlanıyor",
    "SHIPPED": "Kargoya verildi",
    "IN_TRANSIT": "Yolda",
    "DELIVERED": "Teslim edildi",
    "SUCCESS": "Ödeme başarılı",
    "REFUND_PENDING": "İade bekliyor",
    "RETURN_CODE_CREATED": "İade kodu oluşturuldu",
    "UNDER_REVIEW": "İncelemede",
    "PENDING": "Bekliyor",
}


def tr_status(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return STATUS_LABELS.get(text.upper(), text.replace("_", " ").title())


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def _data(item: dict) -> dict:
    return item.get("data") or {}


def _product_names(data: dict) -> str:
    names = [str(item).strip() for item in data.get("items") or [] if str(item).strip()]
    return ", ".join(names[:3])


def _intent_value(classification: Any | None) -> str:
    if classification is None:
        return ""
    parts = [
        getattr(classification, "domain", ""),
        getattr(classification, "intent", ""),
        getattr(classification, "category", ""),
        getattr(classification, "subcategory", ""),
        getattr(classification, "requested_info", ""),
        " ".join(getattr(classification, "requested_information", []) or []),
    ]
    return " ".join(str(part or "").upper() for part in parts)


def build_compact_context(evidence_pack: dict, classification: Any | None = None) -> dict:
    intent_text = _intent_value(classification)
    product_focus = "PRODUCT" in intent_text
    payment_focus = "PAYMENT" in intent_text or "ODEME" in intent_text
    shipping_focus = "SHIP" in intent_text or "KARGO" in intent_text or "DELIVER" in intent_text
    return_focus = "RETURN" in intent_text or "IADE" in intent_text
    order_focus = "ORDER" in intent_text or "SIPARIS" in intent_text or return_focus or shipping_focus

    orders = []
    for item in (evidence_pack.get("order_evidence") or [])[: (3 if order_focus else 1)]:
        data = _data(item)
        parts = [
            _fmt(data.get("order_no")),
            _product_names(data),
            f"sipariş: {tr_status(data.get('order_status'))}" if data.get("order_status") else "",
            f"kargo: {tr_status(data.get('shipping_status'))}" if data.get("shipping_status") else "",
            f"ödeme: {tr_status(data.get('payment_status'))}" if data.get("payment_status") else "",
        ]
        line = " | ".join(part for part in parts if part)
        if line:
            orders.append(line)

    shipments = []
    for item in (evidence_pack.get("shipment_evidence") or [])[: (3 if shipping_focus or order_focus else 1)]:
        data = _data(item)
        parts = [
            _fmt(data.get("order_no")),
            f"kargo: {tr_status(data.get('shipping_status'))}" if data.get("shipping_status") else "",
            f"takip: {_fmt(data.get('tracking_number'))}" if data.get("tracking_number") else "",
            f"tahmini teslimat: {_fmt(data.get('estimated_delivery_at'))}" if data.get("estimated_delivery_at") else "",
        ]
        line = " | ".join(part for part in parts if part)
        if line:
            shipments.append(line)

    returns = []
    for item in (evidence_pack.get("return_evidence") or [])[: (3 if return_focus or order_focus else 1)]:
        data = _data(item)
        parts = [
            _fmt(data.get("order_no")),
            f"iade kodu: {_fmt(data.get('return_code'))}" if data.get("return_code") else "",
            f"iade: {tr_status(data.get('return_status'))}" if data.get("return_status") else "",
            f"geri ödeme: {tr_status(data.get('refund_status'))}" if data.get("refund_status") else "",
        ]
        line = " | ".join(part for part in parts if part)
        if line:
            returns.append(line)

    payments = []
    for item in (evidence_pack.get("payment_evidence") or [])[: (3 if payment_focus else 1)]:
        data = _data(item)
        parts = [
            _fmt(data.get("provider_reference")) or "Ödeme kaydı",
            f"durum: {tr_status(data.get('status'))}" if data.get("status") else "",
            f"tutar: {_fmt(data.get('amount'))}" if data.get("amount") is not None else "",
            f"bağlı sipariş: {_fmt(data.get('order_id'))}" if data.get("order_id") else "bağlı sipariş yok",
        ]
        line = " | ".join(part for part in parts if part)
        if line:
            payments.append(line)

    products = []
    for item in (evidence_pack.get("product_evidence") or [])[: (3 if product_focus else 1)]:
        data = _data(item)
        parts = [
            _fmt(data.get("brand")),
            _fmt(data.get("name")),
            _fmt(data.get("description"))[:180],
            f"fiyat: {_fmt(data.get('price'))} {_fmt(data.get('currency'))}".strip()
            if data.get("price") is not None
            else "",
            f"stok: {_fmt(data.get('stock'))}" if data.get("stock") is not None else "",
            f"garanti: {_fmt(data.get('warranty_months'))} ay"
            if data.get("warranty_months") is not None
            else "",
        ]
        line = " | ".join(part for part in parts if part)
        if line:
            products.append(line)

    policies = []
    review_lines = []
    for item in (evidence_pack.get("review_evidence") or [])[: (3 if product_focus else 1)]:
        data = _data(item)
        rating = data.get("rating_average")
        count = data.get("review_count")
        if rating is not None or count:
            review_lines.append(f"puan: {_fmt(rating)} / 5 | yorum sayisi: {_fmt(count)}")
        for review in (data.get("reviews") or [])[:2]:
            text = " - ".join(
                part
                for part in [
                    _fmt(review.get("rating")),
                    _fmt(review.get("title")),
                    _fmt(review.get("body"))[:120],
                ]
                if part
            )
            if text:
                review_lines.append(text)

    for item in (evidence_pack.get("rag_evidence") or [])[:2]:
        title = str(item.get("title_or_name") or "").strip()
        excerpt = str(item.get("raw_excerpt") or "").strip()
        if title or excerpt:
            policies.append({"title": title, "summary": excerpt[:500]})

    return {
        "orders": orders,
        "shipments": shipments,
        "returns": returns,
        "payments": payments,
        "products": products,
        "reviews": review_lines,
        "policy": policies,
        "missing_evidence": evidence_pack.get("missing_evidence") or [],
        "warnings": evidence_pack.get("warnings") or [],
    }


def compact_policy_text(compact_context: dict) -> str:
    lines = []
    for item in compact_context.get("policy") or []:
        title = item.get("title") or "Destek dokümanı"
        summary = item.get("summary") or ""
        if summary:
            lines.append(f"{title}: {summary[:500]}")
    return "\n\n".join(lines)
