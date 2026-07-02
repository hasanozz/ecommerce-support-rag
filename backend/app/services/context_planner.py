from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_SPEC_PATH = Path(__file__).resolve().parents[3] / "data" / "debug" / "router_db_lookup_plan.json"

_READ_ONLY_ORDER_INTENTS = {
    "ORDER_STATUS",
    "TRACK_ORDER",
    "TRACK_SHIPMENT",
    "DELAYED_DELIVERY",
    "DELIVERY_PROCESS",
    "ESTIMATED_DELIVERY_DATE",
    "MARKED_DELIVERED_NOT_RECEIVED",
    "UNDELIVERED_SHIPMENT",
    "PICKUP_FROM_BRANCH",
}

_ORDER_ACTION_INTENTS = {
    "ORDER_CANCELLATION",
    "CHANGE_ORDER_CONTENT",
    "CHANGE_ORDER_ADDRESS",
    "REDELIVERY_TO_ADDRESS",
    "CHANGE_SHIPPING_COMPANY",
    "SPLIT_ORDER",
    "CHARGED_BUT_ORDER_NOT_CREATED",
    "CREATE_ORDER",
}

_RETURN_ACTION_INTENTS = {
    "CREATE_RETURN_REQUEST",
}

_PRODUCT_READ_ONLY_REQUESTS = {
    "general_info",
    "price",
    "stock",
    "warranty",
    "returnability",
    "technical_specs",
    "comparison",
    "reviews",
    "capacity",
    "material",
    "battery",
    "power",
    "size",
    "tags",
    "category",
}


@lru_cache(maxsize=1)
def load_router_lookup_plan() -> dict:
    if _SPEC_PATH.exists():
        try:
            return json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def normalize_text(value: str | None) -> str:
    return str(value or "").strip().casefold()


def requested_information_set(values: list[str] | None) -> set[str]:
    return {normalize_text(value) for value in (values or []) if normalize_text(value)}


def is_read_only_order_shipping_intent(intent: str | None, subcategory: str | None = None) -> bool:
    intent_value = normalize_text(intent).upper()
    subcategory_value = normalize_text(subcategory).upper()
    if intent_value in _READ_ONLY_ORDER_INTENTS:
        return True
    if subcategory_value in {
        "TRACK_SHIPMENT",
        "DELAYED_DELIVERY",
        "DELIVERY_PROCESS",
        "ESTIMATED_DELIVERY_DATE",
        "MARKED_DELIVERED_NOT_RECEIVED",
        "UNDELIVERED_SHIPMENT",
        "PICKUP_FROM_BRANCH",
    }:
        return True
    return False


def is_action_order_intent(intent: str | None) -> bool:
    return normalize_text(intent).upper() in _ORDER_ACTION_INTENTS | _RETURN_ACTION_INTENTS


def wants_read_only_product_response(requested_information: list[str] | None) -> bool:
    requested = requested_information_set(requested_information)
    return not requested or requested.issubset(_PRODUCT_READ_ONLY_REQUESTS)


def should_use_rag(domain: str | None, intent: str | None, routing_hints: dict | None) -> bool:
    hints = routing_hints or {}
    intent_value = normalize_text(intent).upper()
    domain_value = normalize_text(domain).upper()
    if bool(hints.get("rag_needed")):
        return True
    if domain_value == "SUPPORT" and (
        intent_value.startswith("RETURN_")
        or intent_value in {
            "RETURN_POLICY",
            "RETURN_SHIPPING_PROCESS",
            "RETURN_REJECTION_REASON",
            "PROMOTION_USAGE",
            "COUPON_CODE_USAGE",
            "INVALID_COUPON_ERROR",
            "MINIMUM_CART_AMOUNT",
            "USE_POINTS",
            "EARN_POINTS",
            "PROMOTION_TERMS",
            "ACCOUNT_LOGIN_ISSUE",
            "PASSWORD_RESET",
            "ACCOUNT_CREATION",
            "ACCOUNT_DELETION",
            "EMAIL_CHANGE",
            "PHONE_NUMBER_CHANGE",
            "ACCOUNT_VERIFICATION",
            "TWO_FACTOR_AUTHENTICATION",
            "SUSPICIOUS_LOGIN_REPORT",
            "SUSPICIOUS_LOGIN",
            "SESSION_DEVICE_MANAGEMENT",
            "PERSONAL_DATA_SECURITY",
        }
    ):
        return True
    if domain_value == "MIXED":
        return True
    return False

