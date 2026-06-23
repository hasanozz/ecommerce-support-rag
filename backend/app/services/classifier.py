from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from ..config import Settings, get_settings
from .gemini import GeminiService


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


@dataclass(slots=True)
class ClassificationResult:
    category: Category
    subcategory: str
    priority: Priority
    expected_action: ExpectedAction
    confidence: float | None = None
    provider: str = "rule_based"

    def as_dict(self) -> dict:
        return asdict(self)


class ClassifierProvider(Protocol):
    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult: ...


class RuleBasedClassifier:
    provider_name = "rule_based"
    CATEGORY_TERMS = {
        "IADE": ("iade", "geri gönder", "cayma"),
        "ODEME": ("ödeme", "kart", "para çekildi", "taksit", "fatura"),
        "KARGO_TESLIMAT": ("kargo", "teslim", "paket", "takip"),
        "HESAP_GUVENLIK": ("hesap", "şifre", "giriş", "güvenlik"),
        "KAMPANYA_PUAN": ("kampanya", "puan", "kupon", "indirim"),
        "SIPARIS": ("sipariş", "stok", "ürün", "iptal"),
    }

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        del pii_masked
        lowered = safe_original.casefold()
        category: Category = "GENEL_DESTEK"
        matched_term = ""
        for candidate, terms in self.CATEGORY_TERMS.items():
            matched_term = next((term for term in terms if term in lowered), "")
            if matched_term:
                category = candidate  # type: ignore[assignment]
                break

        urgent_terms = ("hesabım çalındı", "yetkisiz", "dolandırıc", "acil")
        high_terms = ("para çekildi", "teslim edilmedi", "hesaba giremiyorum")
        priority: Priority = "LOW"
        if any(term in lowered for term in urgent_terms):
            priority = "URGENT"
        elif any(term in lowered for term in high_terms):
            priority = "HIGH"
        elif category != "GENEL_DESTEK":
            priority = "MEDIUM"

        action: ExpectedAction = "RAG_ANSWER"
        if len(safe_original.split()) < 2:
            action = "ASK_CLARIFICATION"
        return ClassificationResult(
            category=category,
            subcategory="",
            priority=priority,
            expected_action=action,
            confidence=0.65 if matched_term else 0.4,
            provider=self.provider_name,
        )


class GeminiClassifier:
    provider_name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.gemini = GeminiService(settings)
        self.last_usage: dict = {}

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        del safe_original
        result = await self.gemini.classify(
            pii_masked, use_dev_model=True
        )
        self.last_usage = dict(self.gemini.last_usage)
        return ClassificationResult(
            category=result["category"],
            subcategory=result.get("subcategory", ""),
            priority=result["priority"],
            expected_action=result["expected_action"],
            confidence=result.get("confidence"),
            provider=self.provider_name,
        )


class QwenClassifier:
    """Adapter placeholder. Real Qwen 8B + QLoRA runtime is intentionally absent."""

    provider_name = "qwen"

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        del safe_original, pii_masked
        raise RuntimeError("Qwen classifier modeli henüz yapılandırılmadı.")


class ClassifierService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.rule_based = RuleBasedClassifier()
        self.last_usage: dict = {}

    def _provider(self) -> ClassifierProvider:
        provider = self.settings.classifier_provider.casefold()
        if provider == "gemini":
            return GeminiClassifier(self.settings)
        if provider == "qwen":
            return QwenClassifier()
        return self.rule_based

    async def classify(
        self, safe_original: str, pii_masked: str
    ) -> ClassificationResult:
        provider = self._provider()
        try:
            result = await provider.classify(safe_original, pii_masked)
            self.last_usage = dict(getattr(provider, "last_usage", {}))
            return result
        except Exception:
            if provider is self.rule_based:
                raise
            self.last_usage = {}
            return await self.rule_based.classify(safe_original, pii_masked)
