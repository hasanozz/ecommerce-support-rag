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
    "gramaj": "attribute",
    "gram": "attribute",
    "ml": "capacity",
    "litre": "capacity",
    "fiyat": "price",
    "stok": "stock",
    "yorum": "reviews",
    "kapasite": "capacity",
    "malzeme": "attribute",
    "garanti": "attribute",
    "renk": "attribute",
    "boyut": "attribute",
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


def _requested_information_list(raw_value: object) -> list[str]:
    if isinstance(raw_value, str):
        value = raw_value.strip()
        return [value] if value else []
    if isinstance(raw_value, list):
        values = [str(item).strip() for item in raw_value if str(item).strip()]
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
    value = str(raw or "").strip().upper()
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


def _parse_router_payload(payload: dict, original_message: str) -> ClassificationResult:
    raw = (
        payload.get("raw_model_output")
        or payload.get("router_output")
        or payload.get("parsed_json")
        or payload.get("output")
        or payload
    )
    if not isinstance(raw, dict):
        raise ValueError("Remote router response JSON object degil.")
    domain = str(raw.get("domain") or "").strip().upper() or None
    requested_information = _requested_information_list(
        raw.get("requested_information") or raw.get("requested_info")
    )
    requested_info = _requested_info_scalar(requested_information)
    category = str(raw.get("category") or "").strip().upper() or "GENEL_DESTEK"
    intent = str(raw.get("intent") or "").strip().upper() or "RAG_ANSWER"
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    confidence = raw.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else 0.85
    except (TypeError, ValueError):
        confidence_value = 0.85
    expected_action_raw = str(raw.get("expected_action") or "").strip().upper()
    if expected_action_raw in VALID_EXPECTED_ACTIONS:
        expected_action = expected_action_raw  # type: ignore[assignment]
    elif domain in {"OUT_OF_DOMAIN", "NONSENSE", "UNSAFE"}:
        expected_action = "REJECT"
    elif intent == "UNCLEAR":
        expected_action = "ASK_CLARIFICATION"
    else:
        expected_action = "RAG_ANSWER"
    return ClassificationResult(
        category=category,
        subcategory=str(raw.get("subcategory") or intent or category).strip().upper(),
        priority=_normalize_priority(raw.get("priority")),
        expected_action=expected_action,
        confidence=max(0.0, min(confidence_value, 1.0)),
        provider="qwen_remote",
        domain=domain,
        intent=intent,
        entities={
            "product_id": entities.get("product_id"),
            "product_name": entities.get("product_name"),
            "order_id": entities.get("order_id"),
            "order_no": entities.get("order_no"),
            "coupon_code": entities.get("coupon_code"),
            "category": entities.get("category"),
        },
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

        if has_product_signal and requested_info in {"attribute", "capacity", "price", "stock", "reviews"}:
            product_name = _extract_product_name(safe_original)
            intent = {
                "price": "PRODUCT_PRICE",
                "stock": "PRODUCT_STOCK",
                "reviews": "PRODUCT_REVIEWS",
            }.get(requested_info, "PRODUCT_ATTRIBUTE")
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
                requested_information=[requested_info],
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
                "para Ã§ekildi",
                "kartimdan para",
                "kartÄ±mdan para",
                "ucret cekildi",
                "Ã¼cret Ã§ekildi",
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
        logger.info(
            "remote_qwen_request url=%s request_body=%s",
            self.url,
            json.dumps(request_body, ensure_ascii=False),
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, headers=headers, json=request_body)
        logger.info("remote_qwen_response status_code=%s", response.status_code)
        raw_text = response.text[:500].replace("\n", " ")
        logger.info("remote_qwen_response_raw short=%s", raw_text)
        response.raise_for_status()
        payload = response.json()
        self.last_usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        result = _parse_router_payload(payload if isinstance(payload, dict) else {}, safe_original)
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
        return type(exc).__name__

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        provider = self._provider()
        try:
            result = await provider.classify(safe_original, pii_masked)
            self.last_usage = dict(getattr(provider, "last_usage", {}))
            self.last_provider = getattr(provider, "provider_name", "rule_based")
            self.last_fallback_used = False
            self.last_fallback_reason = ""
            self.last_remote_url = getattr(provider, "url", "")
            self.last_adapter_loaded = bool(getattr(provider, "last_adapter_loaded", False))
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
