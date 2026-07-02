from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Literal, Protocol

import httpx

from ..config import Settings, get_settings


logger = logging.getLogger(__name__)

Category = Literal[
    "SIPARIS",
    "IADE",
    "ODEME",
    "KARGO_TESLIMAT",
    "HESAP_GUVENLIK",
    "KAMPANYA_PUAN",
    "GENEL_DESTEK",
]
Priority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
ExpectedAction = Literal[
    "RAG_ANSWER", "ASK_CLARIFICATION", "REJECT", "CREATE_TICKET"
]

VALID_EXPECTED_ACTIONS = {
    "RAG_ANSWER",
    "ASK_CLARIFICATION",
    "REJECT",
    "CREATE_TICKET",
}
VALID_CATEGORIES = {
    "SIPARIS",
    "IADE",
    "ODEME",
    "KARGO_TESLIMAT",
    "HESAP_GUVENLIK",
    "KAMPANYA_PUAN",
    "GENEL_DESTEK",
}
REMOTE_CATEGORY_ALIASES = {
    "ORDER": "SIPARIS",
    "ORDERS": "SIPARIS",
    "RETURN": "IADE",
    "RETURNS": "IADE",
    "PAYMENT": "ODEME",
    "SHIPPING": "KARGO_TESLIMAT",
    "DELIVERY": "KARGO_TESLIMAT",
    "SHIPPING_DELIVERY": "KARGO_TESLIMAT",
    "ACCOUNT": "HESAP_GUVENLIK",
    "SECURITY": "HESAP_GUVENLIK",
    "CAMPAIGN": "KAMPANYA_PUAN",
    "COUPON": "KAMPANYA_PUAN",
    "PRODUCT": "GENEL_DESTEK",
    "SUPPORT": "GENEL_DESTEK",
}
REMOTE_REQUEST_INFO_ALIASES = {
    "POWER": "attribute",
    "WATT": "attribute",
    "MOTOR_POWER": "attribute",
    "WARRANTY": "warranty",
    "TECHNICAL_SPECS": "attribute",
    "PRODUCT_INFORMATION": "attribute",
    "PRODUCT_INFO": "attribute",
    "RETURNABILITY": "policy",
    "RETURN_ELIGIBILITY": "eligibility",
    "PRODUCT_RETURNABILITY": "eligibility",
    "PRICE": "price",
    "STOCK": "stock",
    "REVIEWS": "reviews",
    "CAPACITY": "capacity",
}
REMOTE_EXPECTED_ACTION_ALIASES = {
    "ANSWER": "RAG_ANSWER",
    "RAG": "RAG_ANSWER",
    "LOOKUP": "RAG_ANSWER",
    "CLARIFY": "ASK_CLARIFICATION",
    "TICKET": "CREATE_TICKET",
}
PROCEDURE_TERMS = (
    "nasil",
    "nasıl",
    "adim",
    "adım",
    "surec",
    "süreç",
    "nereden",
    "basvuru",
    "başvuru",
    "kosul",
    "koşul",
)
ACTION_TERMS = (
    "olustur",
    "oluştur",
    "baslat",
    "başlat",
    "iptal et",
    "ac",
    "aç",
    "yapmak istiyorum",
    "istiyorum",
)
PRODUCT_ATTRIBUTE_TERMS = {
    "watt": "attribute",
    "motor": "attribute",
    "guc": "attribute",
    "gucu": "attribute",
    "gramaj": "attribute",
    "gram": "attribute",
    "ml": "capacity",
    "litre": "capacity",
    "fiyat": "price",
    "stok": "stock",
    "yorum": "reviews",
    "puan": "reviews",
    "degerlendirme": "reviews",
    "değerlendirme": "reviews",
    "kapasite": "capacity",
    "malzeme": "attribute",
    "garanti": "warranty",
    "renk": "attribute",
    "boyut": "attribute",
    "iade": "eligibility",
}
PRODUCT_TERMS = (
    "urun",
    "ürün",
    "blender",
    "powerbank",
    "kahve",
    "sweatshirt",
    "kulaklik",
    "kulaklık",
    "mouse",
    "termos",
    "kupa",
    "mat",
    "filtre",
    "cay",
    "yesil",
)
PRODUCT_INFO_TERMS = (
    "bilgi",
    "hakkinda",
    "hakkında",
    "ozellik",
    "özellik",
    "detay",
    "nedir",
)
SUPPORT_CATEGORY_TERMS: dict[Category, tuple[str, ...]] = {
    "IADE": ("iade", "refund", "geri gonder", "geri gönder", "cayma", "cayma"),
    "SIPARIS": ("siparis", "sipariş", "iptal"),
    "ODEME": ("odeme", "ödeme", "kart", "taksit", "fatura"),
    "KARGO_TESLIMAT": ("kargo", "teslim", "takip", "kurye"),
    "HESAP_GUVENLIK": ("hesap", "sifre", "şifre", "guvenlik", "güvenlik", "giris", "giriş"),
    "KAMPANYA_PUAN": ("kupon", "kampanya", "puan", "indirim"),
}


@dataclass(slots=True)
class ClassificationResult:
    category: Category
    subcategory: str
    priority: Priority
    expected_action: ExpectedAction
    confidence: float | None = None
    provider: str = "rule_based"
    domain: str | None = None
    intent: str | None = None
    entities: dict = field(default_factory=dict)
    requested_info: str | None = None
    requested_information: list[str] = field(default_factory=list)
    routing_hints: dict = field(default_factory=dict)
    doc_id: str | None = None
    raw_router_output: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


class ClassifierProvider(Protocol):
    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult: ...


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _support_category(text: str) -> Category:
    for category, terms in SUPPORT_CATEGORY_TERMS.items():
        if _contains_any(text, terms):
            return category
    return "GENEL_DESTEK"


def _product_requested_info(text: str) -> str | None:
    for term, requested_info in PRODUCT_ATTRIBUTE_TERMS.items():
        if term in text:
            return requested_info
    return None


def _looks_like_product_name(text: str) -> bool:
    tokens = [token for token in re.split(r"[^\wçğıöşü]+", text) if len(token) > 2]
    if not tokens:
        return False
    return sum(1 for token in tokens if token in PRODUCT_TERMS or any(char.isdigit() for char in token)) > 0


def _extract_product_name(original: str) -> str | None:
    cleaned = re.sub(
        r"\b(kaç|kac|watt|gramaj|gram|ml|litre|stok|fiyat|yorum|iade|edilebilir|mi|mı|mu|mü|nasıl|nedir|ne kadar|olur)\b",
        " ",
        original,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,!")
    return cleaned or None


def _clean_product_name(original: str) -> str | None:
    cleaned = _extract_product_name(original) or original
    cleaned = _normalized(cleaned)
    cleaned = re.sub(
        r"\b(kac|watt|motor|guc|gucu|gramaj|gram|ml|litre|stok|fiyat|yorum|puan|iade|garanti|edilebilir|mi|mı|mu|mü|nasil|nedir|ne kadar|olur|hakkinda|bilgi|ozellik|detay)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,!")
    return cleaned or None


def _product_intent(requested_info: str | None, text: str) -> str:
    if requested_info == "price":
        return "PRODUCT_PRICE"
    if requested_info == "stock":
        return "PRODUCT_STOCK"
    if requested_info == "reviews":
        return "PRODUCT_REVIEWS"
    if requested_info in {"policy", "eligibility"}:
        return "PRODUCT_RETURN_ELIGIBILITY"
    if requested_info == "warranty":
        return "PRODUCT_WARRANTY"
    if any(term in text for term in ("iade", "edilebilir")):
        return "PRODUCT_RETURN_ELIGIBILITY"
    return "PRODUCT_ATTRIBUTE"


def _product_requested_information(requested_info: str | None) -> list[str]:
    if not requested_info:
        return ["attribute"]
    if requested_info == "warranty":
        return ["warranty", "attribute"]
    return [requested_info]


def _product_fast_path_result(
    safe_original: str,
    *,
    provider: str,
    original_result: ClassificationResult | None = None,
) -> ClassificationResult | None:
    text = _normalized(safe_original)
    if not text:
        return None
    requested_info = _product_requested_info(text)
    has_product_signal = _looks_like_product_name(text) or any(
        term in text for term in PRODUCT_TERMS
    )
    has_info_intent = any(term in text for term in PRODUCT_INFO_TERMS)
    category = _support_category(text)
    is_product_return = has_product_signal and category == "IADE"
    is_attribute_question = has_product_signal and requested_info is not None
    is_product_info = has_product_signal and has_info_intent and category == "GENEL_DESTEK"
    if not (is_attribute_question or is_product_return or is_product_info):
        return None
    product_name = _clean_product_name(safe_original)
    if not product_name:
        return None
    if is_product_return:
        requested_info = requested_info or "eligibility"
    intent = _product_intent(requested_info, text)
    domain = "MIXED" if is_product_return else "PRODUCT"
    routing_hints = {"product_fast_path": True}
    raw_router_output = {
        "provider": provider,
        "domain": domain,
        "intent": intent,
        "category": "IADE" if is_product_return else "GENEL_DESTEK",
        "subcategory": intent,
        "requested_information": _product_requested_information(requested_info),
        "entities": {"product_name": product_name},
        "routing_hints": routing_hints,
    }
    if original_result is not None:
        routing_hints["product_rescue"] = True
        raw_router_output["original_router"] = original_result.as_dict()
    return ClassificationResult(
        category="IADE" if is_product_return else "GENEL_DESTEK",
        subcategory=intent,
        priority="MEDIUM" if is_product_return else "LOW",
        expected_action="RAG_ANSWER",
        confidence=0.86 if original_result is None else 0.78,
        provider=provider,
        domain=domain,
        intent=intent,
        entities={"product_name": product_name},
        requested_info=requested_info or "attribute",
        requested_information=_product_requested_information(requested_info),
        routing_hints=routing_hints,
        raw_router_output=raw_router_output,
    )


def _requested_information_list(raw_value: object) -> list[str]:
    if isinstance(raw_value, str):
        value = raw_value.strip()
        normalized = REMOTE_REQUEST_INFO_ALIASES.get(value.upper(), value)
        return [normalized] if normalized else []
    if isinstance(raw_value, list):
        values = [
            REMOTE_REQUEST_INFO_ALIASES.get(str(item).strip().upper(), str(item).strip())
            for item in raw_value
            if str(item).strip()
        ]
        return list(dict.fromkeys(values))
    return []


def _requested_info_scalar(values: list[str]) -> str | None:
    if not values:
        return None
    normalized = [value.casefold() for value in values]
    if any(
        token in value
        for value in normalized
        for token in ("procedure", "process", "steps", "how_to", "policy", "eligibility")
    ):
        if any(token in value for value in normalized for token in ("procedure", "process", "steps", "how_to")):
            return "procedure"
        if any(token in value for value in normalized for token in ("policy", "eligibility")):
            return "policy"
    return values[0]


def _normalize_expected_action(raw: object, *, reject: bool = False) -> ExpectedAction:
    value = REMOTE_EXPECTED_ACTION_ALIASES.get(
        str(raw or "").strip().upper(), str(raw or "").strip().upper()
    )
    if value in VALID_EXPECTED_ACTIONS:
        return value  # type: ignore[return-value]
    return "REJECT" if reject else "RAG_ANSWER"


def _normalize_priority(raw: object) -> Priority:
    value = str(raw or "").strip().upper()
    if value in {"LOW", "MEDIUM", "HIGH", "URGENT"}:
        return value  # type: ignore[return-value]
    return "MEDIUM"


def _normalize_category(raw: object, *, text: str, domain: str | None) -> Category:
    value = str(raw or "").strip().upper()
    value = REMOTE_CATEGORY_ALIASES.get(value, value)
    if value in VALID_CATEGORIES:
        return value  # type: ignore[return-value]
    if domain == "PRODUCT":
        return "GENEL_DESTEK"
    return _support_category(text)


def _normalize_intent(
    *,
    raw_intent: object,
    domain: str | None,
    category: Category,
    text: str,
    requested_info: str | None,
) -> str:
    intent = str(raw_intent or "").strip().upper()
    procedure_info = requested_info == "procedure" or _contains_any(text, PROCEDURE_TERMS)
    action_request = _contains_any(text, ACTION_TERMS) and not procedure_info
    if intent in {"OUT_OF_DOMAIN", "NONSENSE"}:
        return "OUT_OF_DOMAIN"
    if intent in {"UNCLEAR"}:
        return "UNCLEAR"
    if domain == "PRODUCT":
        if requested_info == "price":
            return "PRODUCT_PRICE"
        if requested_info == "stock":
            return "PRODUCT_STOCK"
        if requested_info == "reviews":
            return "PRODUCT_REVIEWS"
        if "iade" in text and any(term in text for term in ("olur mu", "edilebilir", "uygun")):
            return "PRODUCT_RETURN_ELIGIBILITY"
        return "PRODUCT_ATTRIBUTE"
    if category == "IADE":
        if procedure_info:
            return "SUPPORT_POLICY_ONLY"
        if action_request:
            return "RETURN_CREATE"
    if category == "SIPARIS":
        if "iptal" in text and not procedure_info:
            return "ORDER_CANCEL"
        if any(term in text for term in ("nerede", "durum", "takip")):
            return "ORDER_STATUS"
    if category == "KARGO_TESLIMAT":
        if any(term in text for term in ("gecik", "gecikti", "gecikme", "hareket")):
            return "ORDER_SHIPPING_DELAY"
        return "ORDER_STATUS" if not procedure_info else "SUPPORT_POLICY_ONLY"
    if category == "ODEME":
        if any(term in text for term in ("sipariş oluşmadı", "siparis olusmadi", "para çekildi", "para cekildi")):
            return "PAYMENT_CHARGED_ORDER_NOT_CREATED"
        return "SUPPORT_POLICY_ONLY"
    if category == "KAMPANYA_PUAN":
        if any(term in text for term in ("gecersiz", "geçersiz", "kullanam", "çalışm")):
            return "COUPON_INVALID"
        if any(term in text for term in ("suresi dol", "süresi dol", "expired")):
            return "COUPON_EXPIRED"
        return "CAMPAIGN_USAGE"
    if domain == "SUPPORT":
        return "SUPPORT_POLICY_ONLY"
    return intent or "SUPPORT_POLICY_ONLY"


def _router_payload_candidate(payload: dict) -> object:
    for key in ("parsed_json", "router_output", "output", "raw_model_output"):
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return payload


def _coerce_router_json(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Remote router JSON parse edilemedi: {exc.msg} at pos {exc.pos}"
            ) from exc
        if isinstance(parsed, dict):
            return parsed
        raise ValueError(
            f"Remote router JSON object bekleniyordu, gelen tip: {type(parsed).__name__}"
        )
    raise ValueError(
        f"Remote router response JSON object degil: {type(value).__name__}"
    )


def _normalize_router_entities(raw: dict, original_message: str) -> dict:
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    product_name = (
        entities.get("product_name")
        or raw.get("product_name")
        or raw.get("product")
    )
    if not product_name and str(raw.get("domain") or "").strip().upper() == "PRODUCT":
        product_name = _extract_product_name(original_message)
    return {
        "product_id": entities.get("product_id") or raw.get("product_id"),
        "product_name": product_name,
        "order_id": entities.get("order_id") or raw.get("order_id"),
        "order_no": entities.get("order_no") or raw.get("order_no"),
        "coupon_code": entities.get("coupon_code") or raw.get("coupon_code"),
        "category": entities.get("category") or raw.get("entity_category"),
    }


def _parse_router_payload(payload: dict, original_message: str) -> ClassificationResult:
    raw = _coerce_router_json(_router_payload_candidate(payload))
    domain = str(raw.get("domain") or "").strip().upper() or None
    requested_information = _requested_information_list(
        raw.get("requested_information") or raw.get("requested_info")
    )
    requested_info = _requested_info_scalar(requested_information)
    category = _normalize_category(raw.get("category"), text=original_message, domain=domain)
    intent = str(raw.get("intent") or "").strip().upper() or "RAG_ANSWER"
    confidence = raw.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else 0.85
    except (TypeError, ValueError):
        confidence_value = 0.85
    expected_action = _normalize_expected_action(
        raw.get("expected_action"),
        reject=domain in {"OUT_OF_DOMAIN", "NONSENSE", "UNSAFE"},
    )
    if intent == "UNCLEAR" and not raw.get("expected_action"):
        expected_action = "ASK_CLARIFICATION"
    provider = str(payload.get("provider") or raw.get("provider") or "qwen_remote").strip()
    entities = _normalize_router_entities(raw, original_message)
    return ClassificationResult(
        category=category,
        subcategory=str(raw.get("subcategory") or intent or category).strip().upper(),
        priority=_normalize_priority(raw.get("priority")),
        expected_action=expected_action,
        confidence=max(0.0, min(confidence_value, 1.0)),
        provider=provider or "qwen_remote",
        domain=domain,
        intent=intent,
        entities=entities,
        requested_info=requested_info,
        requested_information=requested_information,
        routing_hints=raw.get("routing_hints") if isinstance(raw.get("routing_hints"), dict) else {},
        doc_id=str(raw.get("doc_id") or "").strip() or None,
        raw_router_output=raw,
    )


class RuleBasedClassifier:
    provider_name = "rule_based"

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        del pii_masked
        text = _normalized(safe_original)
        category = _support_category(text)
        has_product_signal = _looks_like_product_name(text) or any(term in text for term in PRODUCT_TERMS)
        requested_info = _product_requested_info(text)
        procedure_info = _contains_any(text, PROCEDURE_TERMS)
        action_request = _contains_any(text, ACTION_TERMS) and not procedure_info

        if len(text.split()) < 2:
            return ClassificationResult(
                category=category,
                subcategory="UNCLEAR",
                priority="LOW",
                expected_action="ASK_CLARIFICATION",
                confidence=0.4,
                provider=self.provider_name,
                domain="SUPPORT",
                intent="UNCLEAR",
            )

        if any(term in text for term in ("şiir", "sair", "kod yaz", "şaka", "fıkra")):
            return ClassificationResult(
                category="GENEL_DESTEK",
                subcategory="OUT_OF_DOMAIN",
                priority="LOW",
                expected_action="REJECT",
                confidence=0.9,
                provider=self.provider_name,
                domain="OUT_OF_DOMAIN",
                intent="OUT_OF_DOMAIN",
            )

        if has_product_signal and requested_info in {"attribute", "capacity", "price", "stock", "reviews", "warranty"}:
            product_name = _clean_product_name(safe_original)
            intent = _product_intent(requested_info, text)
            return ClassificationResult(
                category="GENEL_DESTEK",
                subcategory=intent,
                priority="LOW",
                expected_action="RAG_ANSWER",
                confidence=0.82,
                provider=self.provider_name,
                domain="PRODUCT",
                intent=intent,
                entities={"product_name": product_name},
                requested_info=requested_info,
                requested_information=_product_requested_information(requested_info),
            )

        if has_product_signal and category == "IADE":
            return ClassificationResult(
                category="IADE",
                subcategory="PRODUCT_RETURN_ELIGIBILITY",
                priority="MEDIUM",
                expected_action="RAG_ANSWER",
                confidence=0.84,
                provider=self.provider_name,
                domain="MIXED",
                intent="PRODUCT_RETURN_ELIGIBILITY",
                entities={"product_name": _extract_product_name(safe_original)},
                requested_info="policy",
                requested_information=["policy"],
            )

        if procedure_info and category != "GENEL_DESTEK":
            return ClassificationResult(
                category=category,
                subcategory="SUPPORT_POLICY_ONLY",
                priority="MEDIUM",
                expected_action="RAG_ANSWER",
                confidence=0.84,
                provider=self.provider_name,
                domain="SUPPORT",
                intent="SUPPORT_POLICY_ONLY",
                requested_info="procedure",
                requested_information=["procedure"],
            )

        if category == "IADE" and action_request:
            return ClassificationResult(
                category="IADE",
                subcategory="RETURN_CREATE",
                priority="MEDIUM",
                expected_action="RAG_ANSWER",
                confidence=0.8,
                provider=self.provider_name,
                domain="SUPPORT",
                intent="RETURN_CREATE",
                requested_information=["action"],
            )

        if category == "ODEME" and any(
            term in text
            for term in (
                "para cekildi",
                "para çekildi",
                "kartimdan para",
                "kartımdan para",
                "ucret cekildi",
                "ücret çekildi",
            )
        ):
            return ClassificationResult(
                category="ODEME",
                subcategory="PAYMENT_CHARGED_ORDER_NOT_CREATED",
                priority="HIGH",
                expected_action="RAG_ANSWER",
                confidence=0.88,
                provider=self.provider_name,
                domain="SUPPORT",
                intent="PAYMENT_CHARGED_ORDER_NOT_CREATED",
            )

        if category == "SIPARIS" and "iptal" in text and action_request:
            return ClassificationResult(
                category="SIPARIS",
                subcategory="ORDER_CANCEL",
                priority="MEDIUM",
                expected_action="RAG_ANSWER",
                confidence=0.8,
                provider=self.provider_name,
                domain="SUPPORT",
                intent="ORDER_CANCEL",
                requested_information=["action"],
            )

        if category == "KARGO_TESLIMAT":
            return ClassificationResult(
                category="KARGO_TESLIMAT",
                subcategory="ORDER_STATUS",
                priority="MEDIUM",
                expected_action="RAG_ANSWER",
                confidence=0.76,
                provider=self.provider_name,
                domain="SUPPORT",
                intent="ORDER_STATUS" if not procedure_info else "SUPPORT_POLICY_ONLY",
                requested_info="procedure" if procedure_info else None,
                requested_information=["procedure"] if procedure_info else [],
            )

        return ClassificationResult(
            category=category,
            subcategory="SUPPORT_POLICY_ONLY" if category != "GENEL_DESTEK" else "UNCLEAR",
            priority="HIGH" if category == "ODEME" else ("MEDIUM" if category != "GENEL_DESTEK" else "LOW"),
            expected_action="RAG_ANSWER" if category != "GENEL_DESTEK" else "ASK_CLARIFICATION",
            confidence=0.72 if category != "GENEL_DESTEK" else 0.45,
            provider=self.provider_name,
            domain="SUPPORT" if category != "GENEL_DESTEK" else "UNCLEAR",
            intent="SUPPORT_POLICY_ONLY" if category != "GENEL_DESTEK" else "UNCLEAR",
            requested_info="procedure" if procedure_info else None,
            requested_information=["procedure"] if procedure_info else [],
        )


class QwenRemoteClassifier:
    provider_name = "qwen_remote"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.url = self._normalize_url(settings.qwen_remote_router_url or "")
        self.timeout = settings.qwen_remote_router_timeout_seconds or 30
        self.last_usage: dict = {}
        self.last_adapter_loaded = False
        self.last_request_body: dict = {}
        self.last_raw_response: str = ""
        self.last_status_code: int | None = None
        self.last_parsed_output: dict = {}

    @staticmethod
    def _normalize_url(url: str) -> str:
        normalized = url.strip().rstrip("/")
        if not normalized:
            return ""
        if normalized.endswith("/classify"):
            return normalized
        return f"{normalized}/classify"

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        del pii_masked
        if not self.url:
            raise RuntimeError("QWEN_REMOTE_ROUTER_URL tanimli degil.")
        headers = {"content-type": "application/json"}
        request_body = {"message": safe_original}
        self.last_request_body = request_body
        logger.info(
            "remote_qwen_request url=%s request_body=%s",
            self.url,
            json.dumps(request_body, ensure_ascii=False),
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, headers=headers, json=request_body)
        logger.info("remote_qwen_response status_code=%s", response.status_code)
        self.last_status_code = response.status_code
        self.last_raw_response = response.text
        raw_text = response.text[:500].replace("\n", " ")
        logger.info("remote_qwen_response_raw short=%s", raw_text)
        response.raise_for_status()
        payload = response.json()
        self.last_usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        result = _parse_router_payload(payload if isinstance(payload, dict) else {}, safe_original)
        self.last_parsed_output = result.as_dict()
        logger.info(
            "remote_qwen_parsed domain=%s intent=%s requested_information=%s",
            result.domain,
            result.intent,
            json.dumps(result.requested_information, ensure_ascii=False),
        )
        return result


class ClassifierService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.rule_based = RuleBasedClassifier()
        self._remote_qwen: QwenRemoteClassifier | None = None
        self.last_usage: dict = {}
        self.last_provider = "rule_based"
        self.last_fallback_used = False
        self.last_fallback_reason = ""
        self.last_remote_url = ""
        self.last_adapter_loaded = False
        self.last_router_trace: dict = {}

    def _provider_for_name(self, provider_name: str) -> ClassifierProvider:
        provider = provider_name.casefold()
        if provider in {"remote_qwen", "qwen_remote"}:
            if self._remote_qwen is None:
                self._remote_qwen = QwenRemoteClassifier(self.settings)
            return self._remote_qwen
        return self.rule_based

    def _provider(self) -> ClassifierProvider:
        return self._provider_for_name(self.settings.router_provider)

    def _fallback_reason(self, exc: Exception) -> str:
        if isinstance(exc, httpx.TimeoutException):
            return "timeout"
        if isinstance(exc, httpx.HTTPStatusError):
            return f"http_{exc.response.status_code}"
        if isinstance(exc, ValueError):
            return f"parse_error:{exc}"
        return type(exc).__name__

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        fast_path = _product_fast_path_result(
            safe_original, provider="product_fast_path"
        )
        if fast_path is not None:
            self.last_usage = {}
            self.last_provider = fast_path.provider
            self.last_fallback_used = False
            self.last_fallback_reason = ""
            self.last_remote_url = ""
            self.last_adapter_loaded = False
            self.last_router_trace = {
                "provider": self.last_provider,
                "fallback_used": self.last_fallback_used,
                "fallback_reason": self.last_fallback_reason,
                "remote_url": self.last_remote_url,
                "request_body": {},
                "status_code": None,
                "raw_response": "",
                "parsed_output": fast_path.as_dict(),
            }
            logger.info(
                "router_classification provider=%s fallback_used=%s domain=%s intent=%s requested_information=%s",
                self.last_provider,
                self.last_fallback_used,
                fast_path.domain,
                fast_path.intent,
                json.dumps(fast_path.requested_information, ensure_ascii=False),
            )
            return fast_path
        provider = self._provider()
        try:
            result = await provider.classify(safe_original, pii_masked)
            rescue = None
            if (result.domain or "").strip().upper() == "OUT_OF_DOMAIN" or (
                result.intent or ""
            ).strip().upper() == "OUT_OF_DOMAIN":
                rescue = _product_fast_path_result(
                    safe_original,
                    provider="product_rescue",
                    original_result=result,
                )
            if rescue is not None:
                result = rescue
            self.last_usage = dict(getattr(provider, "last_usage", {}))
            self.last_provider = result.provider or getattr(provider, "provider_name", "rule_based")
            self.last_fallback_used = False
            self.last_fallback_reason = ""
            self.last_remote_url = getattr(provider, "url", "")
            self.last_adapter_loaded = bool(getattr(provider, "last_adapter_loaded", False))
            self.last_router_trace = {
                "provider": self.last_provider,
                "fallback_used": self.last_fallback_used,
                "fallback_reason": self.last_fallback_reason,
                "remote_url": self.last_remote_url,
                "request_body": getattr(provider, "last_request_body", {}),
                "status_code": getattr(provider, "last_status_code", None),
                "raw_response": getattr(provider, "last_raw_response", ""),
                "parsed_output": getattr(provider, "last_parsed_output", result.as_dict()),
            }
            logger.info(
                "router_classification provider=%s fallback_used=%s domain=%s intent=%s requested_information=%s",
                self.last_provider,
                self.last_fallback_used,
                result.domain,
                result.intent,
                json.dumps(result.requested_information, ensure_ascii=False),
            )
            return result
        except Exception as exc:
            fallback_provider = self.settings.router_fallback_provider.casefold()
            if provider is self.rule_based or not self.settings.router_fallback_enabled:
                raise
            result = await self._provider_for_name(fallback_provider).classify(
                safe_original, pii_masked
            )
            self.last_usage = {}
            self.last_provider = getattr(self.rule_based, "provider_name", "rule_based")
            self.last_fallback_used = True
            self.last_fallback_reason = self._fallback_reason(exc)
            self.last_remote_url = getattr(provider, "url", "")
            self.last_adapter_loaded = bool(getattr(provider, "last_adapter_loaded", False))
            self.last_router_trace = {
                "provider": self.last_provider,
                "fallback_used": self.last_fallback_used,
                "fallback_reason": self.last_fallback_reason,
                "remote_url": self.last_remote_url,
                "request_body": getattr(provider, "last_request_body", {}),
                "status_code": getattr(provider, "last_status_code", None),
                "raw_response": getattr(provider, "last_raw_response", ""),
                "parsed_output": result.as_dict(),
            }
            logger.info(
                "router_classification provider=%s fallback_used=%s domain=%s intent=%s requested_information=%s fallback_reason=%s",
                self.last_provider,
                self.last_fallback_used,
                result.domain,
                result.intent,
                json.dumps(result.requested_information, ensure_ascii=False),
                self.last_fallback_reason,
            )
            return result
