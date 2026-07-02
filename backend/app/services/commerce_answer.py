from __future__ import annotations

import re
from typing import Any

from .compact_context import tr_status


ACTIVE_RETURN_STATUSES = {
    "CREATED",
    "PENDING",
    "REFUND_PENDING",
    "RETURN_CODE_CREATED",
    "UNDER_REVIEW",
}
CANCELABLE_ORDER_STATUSES = {"PROCESSING", "PREPARING"}
SHIPPED_ORDER_STATUSES = {"SHIPPED", "IN_TRANSIT"}


def _data(item: dict) -> dict:
    return item.get("data") or {}


def _status(data: dict, key: str) -> str:
    return str(data.get(key) or "").strip().upper()


def _first_product(evidence_pack: dict) -> dict:
    items = evidence_pack.get("product_evidence") or []
    return _data(items[0]) if items else {}


def _merged_product(evidence_pack: dict) -> dict:
    merged: dict = {}
    product_id = None
    for item in evidence_pack.get("product_evidence") or []:
        if product_id is None:
            product_id = item.get("source_id") or item.get("entity_id")
        item_id = item.get("source_id") or item.get("entity_id")
        if product_id is not None and item_id not in {None, product_id}:
            continue
        for key, value in _data(item).items():
            if value not in (None, "", [], {}):
                merged[key] = value
    for item in evidence_pack.get("review_evidence") or []:
        item_id = item.get("source_id") or item.get("entity_id")
        if product_id is not None and item_id not in {None, product_id}:
            continue
        for key, value in _data(item).items():
            if value not in (None, "", [], {}):
                merged[key] = value
    return merged or _first_product(evidence_pack)


def _product_list(evidence_pack: dict) -> list[dict]:
    products = []
    seen_ids = set()
    for item in evidence_pack.get("product_evidence") or []:
        item_id = item.get("source_id") or item.get("entity_id")
        if item_id in seen_ids:
            continue
        data = _data(item)
        if data:
            products.append(data)
            seen_ids.add(item_id)
    return products


def _money(product: dict) -> str:
    price = product.get("price")
    if price is None:
        return ""
    currency = product.get("currency") or "TRY"
    return f"{price} {currency}".strip()


def _extract_power_value(product: dict) -> str:
    attributes = product.get("attributes") or {}
    for key in (
        "power_w",
        "power",
        "watt",
        "motor_power",
        "motor_gucu",
        "motor_gücü",
    ):
        value = attributes.get(key)
        if value not in (None, "", [], {}):
            text = str(value).strip()
            return text if "w" in text.casefold() else f"{text}W"
    haystack = " ".join(
        str(product.get(key) or "")
        for key in ("description", "ai_context", "search_text")
    )
    match = re.search(r"(\d{2,5})\s*(w|watt)\b", haystack, flags=re.IGNORECASE)
    return f"{match.group(1)}W" if match else ""


def _attribute_lines(product: dict, limit: int = 4) -> list[str]:
    attributes = product.get("attributes") or {}
    lines = []
    for key, value in attributes.items():
        if value in (None, "", [], {}):
            continue
        label = str(key).replace("_", " ")
        lines.append(f"- {label}: {value}")
        if len(lines) >= limit:
            break
    return lines


def _returnability_answer(product: dict) -> str:
    name = product.get("name") or "Bu ürün"
    returnable = product.get("returnable")
    note = str(product.get("return_policy_note") or "").strip()
    if returnable is True:
        answer = f"{name} için ürün kaydında iade edilebilir görünüyor."
    elif returnable is False:
        answer = f"{name} için ürün kaydında iade edilebilir görünmüyor."
    else:
        answer = f"{name} için iade uygunluğu bilgisi ürün kaydında net değil."
    if note:
        answer = f"{answer} {note}"
    return answer


def _review_answer(product: dict) -> str:
    name = product.get("name") or "Bu ürün"
    rating = product.get("rating_average")
    count = product.get("review_count")
    reviews = product.get("sample_reviews") or product.get("reviews") or []
    distribution = product.get("rating_distribution") or {}
    positive_count = product.get("positive_review_count")
    negative_count = product.get("negative_review_count")
    if rating is None and not count and not reviews:
        return "Bu ürün için henüz yorum yok."
    parts = []
    if rating is not None:
        parts.append(f"ortalama puanı {rating}/5")
    if count:
        parts.append(f"{count} yorum")
    if distribution:
        parts.append(
            "puan dağılımı "
            + ", ".join(f"{key}★: {value}" for key, value in sorted(distribution.items(), reverse=True))
        )
    if positive_count is not None or negative_count is not None:
        parts.append(f"olumlu {positive_count or 0}, olumsuz {negative_count or 0}")
    answer = f"{name} için " + ", ".join(parts) + "."
    review_lines = []
    for review in reviews[:2]:
        body = str(review.get("body") or "").strip()
        title = str(review.get("title") or "").strip()
        rating_text = str(review.get("rating") or "").strip()
        text = " - ".join(part for part in (rating_text, title, body) if part)
        if text:
            review_lines.append(f"- {text}")
    if review_lines:
        answer = f"{answer}\nÖne çıkan yorumlar:\n" + "\n".join(review_lines)
    return answer


def _full_product_profile_answer(product: dict) -> str:
    name = product.get("name") or "Ürün"
    lines = [f"{name} için ürün profili:"]
    brand = product.get("brand")
    category = product.get("category")
    description = product.get("description")
    if brand:
        lines.append(f"- Marka: {brand}")
    if category:
        lines.append(f"- Kategori: {category}")
    if description:
        lines.append(f"- Açıklama: {description}")
    attributes = _attribute_lines(product, limit=5)
    if attributes:
        lines.append("- Teknik özellikler:")
        lines.extend(attributes)
    price = _money(product)
    if price:
        lines.append(f"- Fiyat: {price}")
    if product.get("stock") is not None:
        lines.append(f"- Stok: {product.get('stock')}")
    lines.append(f"- İade: {_returnability_answer(product)}")
    warranty_months = product.get("warranty_months")
    warranty_note = str(product.get("warranty_note") or "").strip()
    if warranty_months is not None:
        warranty = f"{warranty_months} ay"
        if warranty_note:
            warranty = f"{warranty}. {warranty_note}"
        lines.append(f"- Garanti: {warranty}")
    elif warranty_note:
        lines.append(f"- Garanti: {warranty_note}")
    else:
        lines.append("- Garanti: Garanti bilgisi bulunamadı.")
    lines.append(f"- Yorumlar: {_review_answer(product)}")
    return "\n".join(lines)


def _product_group_answer(products: list[dict], question_l: str) -> str:
    wants_price = "fiyat" in question_l or "ne kadar" in question_l or "kaç para" in question_l
    lines = []
    for product in products[:5]:
        name = product.get("name") or "Ürün"
        price = _money(product)
        stock = product.get("stock")
        if wants_price and price:
            line = f"- {name}: {price}"
        else:
            line = f"- {name}"
            if price:
                line += f", fiyat {price}"
        if stock is not None:
            line += f", stok {stock}"
        lines.append(line)
    if len(products) > 5:
        lines.append(f"- Ayrıca {len(products) - 5} ürün daha var.")
    return "İlgili ürünler şöyle:\n" + "\n".join(lines) if lines else "Bu ürün grubu için ürün bulunamadı."


def _product_answer(
    *,
    product: dict,
    requested: set[str],
    requested_info: str,
    question_l: str,
    answer_mode: str = "",
) -> str:
    name = product.get("name") or "Ürün"
    if answer_mode == "FULL_PRODUCT_PROFILE":
        return _full_product_profile_answer(product)
    wants_power = (
        {"power", "watt", "motor_power", "motor_gucu", "attribute"} & requested
        or requested_info in {"power", "watt", "motor_power", "motor_gucu", "attribute", "capacity"}
        or "watt" in question_l
        or "motor gücü" in question_l
        or "motor gucu" in question_l
    )
    wants_price = "price" in requested or requested_info == "price" or "fiyat" in question_l
    wants_stock = "stock" in requested or requested_info == "stock" or "stok" in question_l
    wants_return = (
        {"policy", "eligibility"} & requested
        or requested_info in {"policy", "eligibility"}
        or "iade" in question_l
    )
    wants_warranty = "warranty" in requested or requested_info == "warranty" or "garanti" in question_l
    wants_reviews = (
        "reviews" in requested
        or requested_info == "reviews"
        or "yorum" in question_l
        or "puan" in question_l
        or "değerlendirme" in question_l
        or "degerlendirme" in question_l
    )
    if wants_reviews:
        return _review_answer(product)
    if wants_price:
        value = _money(product)
        return f"{name} fiyatı {value}." if value else f"{name} için fiyat bilgisi bulunamadı."
    if wants_stock:
        stock = product.get("stock")
        if stock is None:
            return f"{name} için stok bilgisi bulunamadı."
        return f"{name} için stok adedi {stock}."
    if wants_return:
        return _returnability_answer(product)
    if wants_warranty:
        months = product.get("warranty_months")
        note = str(product.get("warranty_note") or "").strip()
        if months is None and not note:
            return f"{name} için garanti bilgisi bulunamadı."
        answer = f"{name} için garanti süresi {months} ay." if months is not None else f"{name} için garanti bilgisi mevcut."
        return f"{answer} {note}".strip()
    if wants_power:
        power = _extract_power_value(product)
        if power:
            return f"{name} için motor gücü {power}."
    lines = []
    brand = product.get("brand")
    description = product.get("description")
    if brand:
        lines.append(f"Marka: {brand}")
    if description:
        lines.append(str(description))
    lines.extend(_attribute_lines(product))
    price = _money(product)
    if price:
        lines.append(f"Fiyat: {price}")
    if product.get("stock") is not None:
        lines.append(f"Stok: {product.get('stock')}")
    return f"{name} için mevcut ürün bilgisi:\n" + "\n".join(lines) if lines else f"{name} için ürün bilgisi bulunamadı."


def _policy_answer(evidence_pack: dict) -> str:
    for item in evidence_pack.get("rag_evidence") or []:
        title = str(item.get("title_or_name") or "").strip()
        excerpt = str(item.get("raw_excerpt") or "").strip()
        if not excerpt:
            continue
        lines = [
            line.strip(" -")
            for line in excerpt.splitlines()
            if line.strip().startswith("-")
        ]
        if lines:
            return f"{title} bilgisine göre:\n" + "\n".join(
                f"- {line}" for line in lines[:6]
            )
        return f"{title} bilgisine göre: {excerpt[:500].strip()}"
    return ""


def _return_by_order(evidence_pack: dict) -> dict[str, dict]:
    result = {}
    for item in evidence_pack.get("return_evidence") or []:
        data = _data(item)
        order_no = str(data.get("order_no") or "").strip()
        if order_no:
            result[order_no] = data
    return result


def _shipment_by_order(evidence_pack: dict) -> dict[str, dict]:
    result = {}
    for item in evidence_pack.get("shipment_evidence") or []:
        data = _data(item)
        order_no = str(data.get("order_no") or "").strip()
        if order_no:
            result[order_no] = data
    return result


def _order_lines(evidence_pack: dict, *, intent: str) -> list[str]:
    returns = _return_by_order(evidence_pack)
    shipments = _shipment_by_order(evidence_pack)
    lines = []
    for item in (evidence_pack.get("order_evidence") or [])[:3]:
        data = _data(item)
        order_no = str(data.get("order_no") or "").strip()
        if not order_no:
            continue
        order_status = _status(data, "order_status")
        shipping_status = _status(data, "shipping_status")
        return_data = returns.get(order_no)
        shipment = shipments.get(order_no) or {}
        prefix = f"{order_no}"
        if data.get("items"):
            prefix += f" ({', '.join(str(name) for name in data.get('items', [])[:2])})"
        if return_data and _status(return_data, "return_status") in ACTIVE_RETURN_STATUSES:
            code = return_data.get("return_code") or "iade kodu yok"
            status = tr_status(return_data.get("return_status"))
            lines.append(f"- {prefix}: Zaten iade sürecinde. İade kodu {code}, durum {status}.")
        elif order_status in CANCELABLE_ORDER_STATUSES:
            lines.append(f"- {prefix}: Sipariş {tr_status(order_status)}; iptal edilebilir.")
        elif order_status in SHIPPED_ORDER_STATUSES or shipping_status in SHIPPED_ORDER_STATUSES:
            lines.append(
                f"- {prefix}: Sipariş {tr_status(order_status or shipping_status)}; iptal edilemez, teslimattan sonra iade talebi açılabilir."
            )
        elif order_status == "DELIVERED" or shipping_status == "DELIVERED":
            tracking = shipment.get("tracking_number")
            if intent in {"DELIVERED_NOT_RECEIVED", "MARKED_DELIVERED_NOT_RECEIVED"}:
                suffix = f" Takip numarası {tracking}." if tracking else ""
                lines.append(f"- {prefix}: Teslim edildi görünüyor; teslim almadıysanız inceleme/destek süreci gerekir.{suffix}")
            else:
                lines.append(f"- {prefix}: Teslim edildi; aktif iade yoksa iade talebi oluşturulabilir.")
        else:
            lines.append(
                f"- {prefix}: Sipariş durumu {tr_status(order_status)}, kargo durumu {tr_status(shipping_status)}."
            )
    return lines


def _payment_answer(evidence_pack: dict) -> str:
    payments = evidence_pack.get("payment_evidence") or []
    if not payments:
        return "Bu kullanıcı için eşleşen ödeme kaydı bulunamadı."
    lines = []
    for item in payments[:3]:
        data = _data(item)
        status = _status(data, "status")
        ref = data.get("provider_reference") or "Ödeme kaydı"
        if status == "SUCCESS" and not data.get("order_id"):
            lines.append(f"- {ref}: Ödeme başarılı görünüyor ancak bağlı sipariş bulunamadı; destek incelemesi gerekir.")
        else:
            lines.append(f"- {ref}: Durum {tr_status(status)}, tutar {data.get('amount')}.")
    return "Ödeme kayıtlarınızda durum şöyle:\n" + "\n".join(lines)


def _is_account_linked_product_flow(
    *, category: str, intent: str, expected_action: str, question_l: str
) -> bool:
    commerce_intent = f"{intent} {expected_action}".upper()
    if category in {"SIPARIS", "KARGO_TESLIMAT", "ODEME"}:
        return True
    if any(term in commerce_intent for term in ("ORDER", "SHIPPING", "PAYMENT", "REFUND")):
        return True
    if category == "IADE" and any(
        term in question_l
        for term in ("durum", "kod", "talep", "başlat", "baslat", "oluştur", "olustur")
    ):
        return True
    return False


def _product_answer_mode(
    *,
    evidence_pack: dict,
    requested: set[str],
    requested_info: str,
    question_l: str,
    category: str,
    intent: str,
    expected_action: str,
) -> str:
    product_resolution = evidence_pack.get("product_resolution") or {}
    frontend_context = evidence_pack.get("frontend_context") or {}
    general_profile_request = any(
        term in question_l for term in ("bilgi", "hakkında", "hakkinda", "detay")
    )
    if product_resolution.get("selected_group"):
        return "PRODUCT_GROUP"
    if (
        "reviews" in requested
        or requested_info == "reviews"
        or any(term in question_l for term in ("yorum", "puan", "değerlendirme", "degerlendirme"))
    ):
        return "PRODUCT_REVIEW"
    if _is_account_linked_product_flow(
        category=category,
        intent=intent,
        expected_action=expected_action,
        question_l=question_l,
    ):
        return "ACCOUNT_LINKED_PRODUCT"
    if (
        frontend_context.get("page_context") == "product"
        and frontend_context.get("current_product_id")
        and (
            (not requested and requested_info not in {"price", "stock", "policy", "eligibility", "warranty", "capacity"})
            or (
                general_profile_request
                and requested <= {"attribute"}
                and requested_info in {"", "attribute"}
            )
        )
    ):
        return "FULL_PRODUCT_PROFILE"
    if product_resolution.get("product_id_source") == "current_product_id" and not requested and not requested_info:
        return "FULL_PRODUCT_PROFILE"
    if "price" in requested or requested_info == "price" or "fiyat" in question_l:
        return "PRODUCT_PRICE"
    return "PRODUCT"


def build_deterministic_answer(
    *,
    question: str,
    classification: Any,
    evidence_pack: dict,
    compact_context: dict,
) -> dict:
    del compact_context
    intent = str(getattr(classification, "intent", "") or "").strip().upper()
    expected_action = str(getattr(classification, "expected_action", "") or "").strip().upper()
    category = str(getattr(classification, "category", "") or "").strip().upper()
    domain = str(getattr(classification, "domain", "") or "").strip().upper()
    requested = {
        str(item).strip().casefold()
        for item in (getattr(classification, "requested_information", []) or [])
        if str(item).strip()
    }
    requested_info = str(getattr(classification, "requested_info", "") or "").casefold()
    question_l = question.casefold()

    products = _product_list(evidence_pack)
    product_group = evidence_pack.get("product_resolution", {}).get("selected_group") or {}
    if product_group and len(products) > 1:
        return {
            "answer": _product_group_answer(products, question_l),
            "source": "deterministic_product_group",
            "answer_mode": "PRODUCT_GROUP",
        }

    product = _merged_product(evidence_pack)
    product_answer_mode = _product_answer_mode(
        evidence_pack=evidence_pack,
        requested=requested,
        requested_info=requested_info,
        question_l=question_l,
        category=category,
        intent=intent,
        expected_action=expected_action,
    )
    if product and (
        intent.startswith("PRODUCT_")
        or domain in {"PRODUCT", "MIXED"}
        or category == "PRODUCT"
        or bool((evidence_pack.get("product_resolution") or {}).get("selected_product"))
        or bool((evidence_pack.get("frontend_context") or {}).get("current_product_id"))
        or requested
        or any(term in question_l for term in ("watt", "fiyat", "stok", "iade", "garanti", "yorum", "puan"))
    ):
        product_answer = _product_answer(
            product=product,
            requested=requested,
            requested_info=requested_info,
            question_l=question_l,
            answer_mode=product_answer_mode,
        )
        if product_answer_mode == "ACCOUNT_LINKED_PRODUCT" and category == "IADE" and (
            evidence_pack.get("order_evidence")
            or evidence_pack.get("return_evidence")
            or evidence_pack.get("shipment_evidence")
        ):
            lines = _order_lines(evidence_pack, intent=intent)
            if lines:
                user_part = "Sizin kayıtlarınızda durum şöyle:\n" + "\n".join(lines)
                product_answer = _join(product_answer, user_part)
        elif (
            product_answer_mode == "ACCOUNT_LINKED_PRODUCT"
            and evidence_pack.get("product_order_filter", {}).get("enabled")
            and not evidence_pack.get("order_evidence")
        ):
            product_answer = _join(
                product_answer,
                "Hesabınızda bu ürüne ait sipariş kaydı görünmüyor.",
            )
        return {
            "answer": product_answer,
            "source": "deterministic_product",
            "answer_mode": product_answer_mode,
        }
    if product and (
        intent.startswith("PRODUCT_")
        or domain in {"PRODUCT", "MIXED"}
        or category == "PRODUCT"
        or {"power", "watt", "motor_power", "motor_gucu"} & requested
        or requested_info in {"power", "watt", "motor_power", "motor_gucu"}
        or "watt" in question_l
        or "motor gücü" in question_l
        or "motor gucu" in question_l
    ):
        name = product.get("name") or "Ürün"
        power = _extract_power_value(product)
        if power:
            return {
                "answer": f"{name} için motor gücü {power}.",
                "source": "deterministic_product",
                "answer_mode": "PRODUCT",
            }
        if product.get("description"):
            return {
                "answer": f"{name} için mevcut ürün bilgisi: {product.get('description')}",
                "source": "deterministic_product",
                "answer_mode": "PRODUCT",
            }

    policy = _policy_answer(evidence_pack)
    commerce_intent = intent or expected_action
    if category in {"ODEME"} or "PAYMENT" in commerce_intent or "ödeme" in question_l:
        return {
            "answer": _join(policy, _payment_answer(evidence_pack)),
            "source": "deterministic_payment",
            "answer_mode": "ACCOUNT_LINKED_PRODUCT",
        }

    if category in {"IADE", "SIPARIS", "KARGO_TESLIMAT"} or commerce_intent in {
        "RETURN_CREATE",
        "CREATE_RETURN_REQUEST",
        "ORDER_CANCEL",
        "ORDER_CANCELLATION",
        "ORDER_STATUS",
        "SHIPPING_DELIVERY",
        "DELIVERED_NOT_RECEIVED",
        "MARKED_DELIVERED_NOT_RECEIVED",
    }:
        lines = _order_lines(evidence_pack, intent=commerce_intent)
        if lines:
            user_part = "Sizin kayıtlarınızda durum şöyle:\n" + "\n".join(lines)
        else:
            user_part = "Bu kullanıcı için ilgili sipariş, iade veya kargo kaydı bulunamadı."
        return {
            "answer": _join(policy, user_part),
            "source": "deterministic_commerce",
            "answer_mode": "ACCOUNT_LINKED_PRODUCT",
        }

    if policy:
        return {"answer": policy, "source": "deterministic_policy", "answer_mode": "POLICY"}

    return {
        "answer": "Bu kullanıcı için ilgili kayıt veya kaynak bulunamadı.",
        "source": "deterministic_no_evidence",
        "answer_mode": "NO_EVIDENCE",
    }


def _join(first: str, second: str) -> str:
    if first and second:
        return f"{first}\n\n{second}"
    return first or second
