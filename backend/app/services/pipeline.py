from __future__ import annotations

import time
import re
from decimal import Decimal
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from ..config import Settings, get_settings
from ..models import Chunk, Conversation, Document, Message, RagRun, User
from ..schemas.context_resolver import ContextResolverOutput
from ..schemas.data_resolver import (
    DataResolutionStatus,
    DataResolverOutput,
    EntityType,
    ResolutionNextStep,
)
from ..schemas.evidence_fetcher import EvidenceFetcherOutput
from .gemini import GeminiService, GeminiServiceError, guard_llm_output
from .ai_contracts import ContextBuilder, PassthroughReranker
from .classifier import ClassificationResult, ClassifierService
from .confidence import composite_confidence, confidence_label
from .context_resolver import ContextResolver
from .data_resolver import DataResolver, SqlAlchemyDataResolverAdapter
from .evidence_fetcher import EvidenceFetcher, SqlAlchemyEvidenceFetcherAdapter
from .demo_commerce import CustomerContextService
from .product_context import ProductContextService
from .privacy import mask_pii
from .retrieval import GroupedDocument, RetrievalService
from .similar import SimilarSolutionService


ORDER_NO_PATTERN = re.compile(r"\bDMO-[A-Za-z0-9-]+\b", re.IGNORECASE)
COUPON_CODE_PATTERN = re.compile(r"\b[A-ZÇĞİÖŞÜ0-9][A-ZÇĞİÖŞÜ0-9_-]{3,31}\b")
CONTEXT_ORDER_PATTERN = re.compile(r"Sipariş\s+(DMO-[^:\s]+)", re.IGNORECASE)
ORDINAL_REFERENCES = {
    1: ("1", "1.", "birinci", "ilk", "1. olan", "birinci olan", "ilk olan"),
    2: ("2", "2.", "ikinci", "2. olan", "ikinci olan", "2 olan"),
    3: ("3", "3.", "üçüncü", "ucuncu", "3. olan", "üçüncü olan", "3 olan"),
}
FOLLOWUP_HINTS = (
    "bu",
    "bunu",
    "bunun",
    "ona",
    "onu",
    "onun",
    "o zaman",
    "peki",
    "tamam",
    "devam",
    "seçtim",
    "seçtim",
    "seçiyorum",
    "ne zaman",
    "nerede",
    "nerde",
    "nasıl",
    "olur mu",
    "edebilir miyim",
    "ne yapmalıyım",
    "son durum",
    "kaç gün",
    "ne kadar",
    "geldi mi",
    "oldu mu",
    "açabilir miyim",
    "yapabilir miyim",
)


class SupportPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.gemini = GeminiService(self.settings)
        self.rewriter = self.gemini
        self.retrieval = RetrievalService()
        self.similar = SimilarSolutionService(settings=self.settings)
        self.classifier = ClassifierService(self.settings)
        self.context_resolver = ContextResolver()
        self.data_resolver: DataResolver | None = None
        self.evidence_fetcher: EvidenceFetcher | None = EvidenceFetcher(
            SqlAlchemyEvidenceFetcherAdapter()
        )
        self.customer_context = CustomerContextService()
        self.product_context = ProductContextService()
        self.reranker = PassthroughReranker()
        self.context_builder = ContextBuilder()

    def _normalize_citations(
        self, raw_citations: list[str], allowed_sources: list[dict]
    ) -> tuple[list[str], list[str], bool]:
        allowed_ids = {source["doc_id"] for source in allowed_sources}
        title_to_ids: dict[str, list[str]] = {}
        for source in allowed_sources:
            title = str(source.get("title", "")).strip().casefold()
            if title:
                title_to_ids.setdefault(title, []).append(source["doc_id"])

        normalized: list[str] = []
        invalid: list[str] = []
        citation_normalized = False
        for raw in raw_citations:
            value = str(raw).strip()
            if not value:
                continue
            if value in allowed_ids:
                normalized.append(value)
                continue
            matching_ids = title_to_ids.get(value.casefold(), [])
            if len(matching_ids) == 1:
                normalized.append(matching_ids[0])
                citation_normalized = True
                continue
            invalid.append(value)
        return list(dict.fromkeys(normalized)), invalid, citation_normalized

    def _extract_order_no(self, text: str) -> str | None:
        match = ORDER_NO_PATTERN.search(text)
        return match.group(0).upper() if match else None

    def _extract_ordinal_reference(self, text: str) -> int | None:
        normalized = text.casefold().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        for index, terms in ORDINAL_REFERENCES.items():
            if normalized in terms:
                return index
            word_terms = [term for term in terms if not term[0].isdigit()]
            if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in word_terms):
                return index
            if re.search(rf"\b{index}\.?\s*(olan|sipariş|siradaki|sıradaki)\b", normalized):
                return index
        return None

    def _context_order_numbers(self, previous_context: dict) -> list[str]:
        items = previous_context.get("items", []) if previous_context else []
        order_numbers = []
        for item in items:
            match = CONTEXT_ORDER_PATTERN.search(item)
            if match:
                order_numbers.append(match.group(1).upper())
        return order_numbers

    def _is_contextual_followup(self, text: str, previous_context: dict) -> bool:
        if not previous_context.get("text") and not previous_context.get("items"):
            return False
        normalized = re.sub(r"\s+", " ", text.casefold()).strip()
        if not normalized:
            return False
        if self._extract_order_no(normalized) or self._extract_ordinal_reference(normalized):
            return True
        if any(re.search(rf"(?<!\w){re.escape(hint)}(?!\w)", normalized) for hint in FOLLOWUP_HINTS):
            return True
        return False

    def _infer_context_intent(
        self,
        classification: ClassificationResult,
        query: str,
        *,
        is_in_scope: bool,
    ) -> str:
        if classification.intent:
            return classification.intent.strip().upper()
        if classification.expected_action == "REJECT":
            return "UNSAFE"
        if not is_in_scope:
            return "OUT_OF_DOMAIN"

        normalized = re.sub(r"\s+", " ", query.casefold()).strip()
        if "para çekildi" in normalized and (
            "sipariş oluşmadı" in normalized or "siparişim oluşmadı" in normalized
        ):
            return "PAYMENT_CHARGED_ORDER_NOT_CREATED"
        if "yorum" in normalized or "puan" in normalized:
            return "PRODUCT_REVIEWS"
        if "stok" in normalized or "mevcut mu" in normalized:
            return "PRODUCT_STOCK"
        if any(term in normalized for term in ("fiyat", "kaç tl", "kaç lira")):
            return "PRODUCT_PRICE"
        if any(term in normalized for term in ("kaç ml", "hacim", "kapasite", "özellik")):
            return "PRODUCT_ATTRIBUTE"
        if "iade" in normalized and any(
            term in normalized for term in ("olur mu", "edilebilir", "uygun mu")
        ):
            return "PRODUCT_RETURN_ELIGIBILITY"
        if "iade" in normalized and any(
            term in normalized for term in ("oluştur", "başlat", "etmek istiyorum")
        ):
            return "RETURN_CREATE"
        if "iptal" in normalized and "sipariş" in normalized:
            return "ORDER_CANCEL"
        if any(term in normalized for term in ("gecikti", "gecikme", "hareketi yok")):
            return "ORDER_SHIPPING_DELAY"
        if "teslim" in normalized and any(
            term in normalized for term in ("almadım", "gelmedi", "ulaşmadı")
        ):
            return "DELIVERED_NOT_RECEIVED"
        if "kupon" in normalized and any(
            term in normalized for term in ("geçersiz", "çalışmıyor", "kullanamıyorum")
        ):
            return "COUPON_INVALID"
        if "kupon" in normalized and any(
            term in normalized for term in ("süresi dol", "expired", "sona er")
        ):
            return "COUPON_EXPIRED"
        if "kampanya" in normalized:
            return "CAMPAIGN_USAGE"
        if "sipariş" in normalized and any(
            term in normalized for term in ("nerede", "durum", "ne oldu")
        ):
            return "ORDER_STATUS"
        if classification.expected_action == "ASK_CLARIFICATION":
            return "UNCLEAR"
        return "SUPPORT_POLICY_ONLY"

    @staticmethod
    def _explicit_product_reference(query: str, intent: str) -> str | None:
        if not intent.startswith("PRODUCT_"):
            return None
        candidate = query.casefold()
        removable_phrases = (
            "kaç ml",
            "stokta mı",
            "mevcut mu",
            "yorumları nasıl",
            "yorumlar nasıl",
            "fiyatı ne kadar",
            "fiyatı nedir",
            "iade olur mu",
            "iade edilebilir mi",
            "bu ürün",
            "o ürün",
        )
        for phrase in removable_phrases:
            candidate = candidate.replace(phrase, " ")
        candidate = re.sub(r"[^\wçğıöşü]+", " ", candidate).strip()
        if candidate in {"", "ürün", "bunun", "bunu", "kaç", "nasıl"}:
            return None
        return candidate

    @staticmethod
    def _explicit_order_product_reference(query: str, intent: str) -> str | None:
        if intent not in {
            "ORDER_STATUS",
            "ORDER_CANCEL",
            "ORDER_SHIPPING_DELAY",
            "DELIVERED_NOT_RECEIVED",
            "RETURN_CREATE",
        }:
            return None
        candidate = query.casefold()
        candidate = re.sub(
            r"\b(siparişim|siparişimi|sipariş|nerede|durumu|iptal|etmek|istiyorum|"
            r"gecikti|gecikme|teslim|edildi|edilmedi|almadım|gelmedi|iade|oluştur|başlat)\b",
            " ",
            candidate,
        )
        candidate = re.sub(r"[^\wçğıöşü]+", " ", candidate).strip()
        return candidate or None

    def _context_resolver_input(
        self,
        classification: ClassificationResult,
        message: str,
        *,
        canonical_query: str,
        is_in_scope: bool,
        conversation_state: object | None,
        frontend_context: dict,
        followup_reference: dict,
    ) -> dict:
        entities = dict(classification.entities or {})
        intent = self._infer_context_intent(
            classification, canonical_query, is_in_scope=is_in_scope
        )
        if frontend_context.get("current_product_id"):
            entities["product_id"] = frontend_context["current_product_id"]
        if frontend_context.get("current_order_id"):
            entities["order_id"] = frontend_context["current_order_id"]
        if followup_reference.get("order_no"):
            entities["order_no"] = followup_reference["order_no"]
        if not entities.get("order_no"):
            entities["order_no"] = self._extract_order_no(canonical_query)
        if not entities.get("coupon_code"):
            coupon_match = COUPON_CODE_PATTERN.search(message)
            if coupon_match and "kupon" in message.casefold():
                entities["coupon_code"] = coupon_match.group(0)
        if not entities.get("product_id") and not entities.get("product_name"):
            entities["product_name"] = self._explicit_product_reference(
                canonical_query, intent
            ) or self._explicit_order_product_reference(canonical_query, intent)

        requested_info = classification.requested_info
        if not requested_info and any(
            term in canonical_query.casefold() for term in ("kaç ml", "hacim", "kapasite")
        ):
            requested_info = "capacity"
        confidence = classification.confidence or 0.0
        return {
            "message": message,
            "classifier_output": {
                "domain": classification.domain,
                "intent": intent,
                "category": classification.category,
                "subcategory": classification.subcategory,
                "doc_id": classification.doc_id,
                "entities": entities,
                "requested_info": requested_info,
                "confidence": confidence,
            },
            "conversation_state": {
                "last_product_id": getattr(conversation_state, "last_product_id", None),
                "last_order_id": getattr(conversation_state, "last_order_id", None),
                "last_intent": getattr(conversation_state, "last_intent", None),
                "last_action": getattr(conversation_state, "last_action", None),
            },
        }

    @staticmethod
    def _resolver_clarification_message(reason: str | None) -> str:
        if reason in {"PRODUCT_CONTEXT_REQUIRED", "PRODUCT_NAME_COULD_NOT_BE_RESOLVED"}:
            return "Hangi ürünü kastettiğinizi ürün adı veya ürün sayfası ile netleştirir misiniz?"
        if reason in {"ORDER_CONTEXT_REQUIRED", "ORDER_REFERENCE_COULD_NOT_BE_RESOLVED"}:
            return "Hangi siparişi kastettiğinizi sipariş numarasıyla netleştirir misiniz?"
        if reason == "COUPON_CODE_REQUIRED":
            return "Kontrol etmemi istediğiniz kupon kodunu paylaşır mısınız?"
        return "Sorunuzu doğru yönlendirebilmem için hangi işlemle ilgili olduğunu netleştirir misiniz?"

    @staticmethod
    def _should_run_support_rag(
        *, needs_support_rag: bool, support_in_scope: bool, route_mode: str
    ) -> bool:
        return needs_support_rag and support_in_scope and route_mode != "product_only"

    @staticmethod
    def _context_plan_metadata(context_plan: ContextResolverOutput) -> dict:
        return context_plan.model_dump(mode="json")

    @staticmethod
    def _data_resolver_input(
        *,
        user_id: int,
        message: str,
        context_plan: ContextResolverOutput,
        conversation_state: object | None,
        frontend_context: dict,
    ) -> dict:
        return {
            "user_id": user_id,
            "message": message,
            "context_plan": context_plan.model_dump(mode="json"),
            "conversation_state": {
                "last_product_id": getattr(conversation_state, "last_product_id", None),
                "last_order_id": getattr(conversation_state, "last_order_id", None),
                "last_cart_id": getattr(conversation_state, "last_cart_id", None),
                "last_payment_id": getattr(conversation_state, "last_payment_id", None),
                "last_intent": getattr(conversation_state, "last_intent", None),
                "last_action": getattr(conversation_state, "last_action", None),
            },
            "frontend_context": {
                key: frontend_context[key]
                for key in (
                    "current_product_id",
                    "current_order_id",
                    "current_cart_id",
                    "current_payment_id",
                    "page_context",
                )
                if frontend_context.get(key) is not None
            },
        }

    @staticmethod
    def _data_resolution_allows_context(result: DataResolverOutput) -> bool:
        if result.status in {DataResolutionStatus.RESOLVED, DataResolutionStatus.SKIP}:
            return True
        return (
            result.status == DataResolutionStatus.PARTIALLY_RESOLVED
            and not result.missing_entities
            and not result.ambiguous_entities
            and not result.unfulfilled_contexts
        )

    @staticmethod
    def _data_resolution_clarification_message(result: DataResolverOutput) -> str:
        if result.status == DataResolutionStatus.AMBIGUOUS:
            return "Birden fazla olası kayıt buldum. Hangisini kastettiğinizi netleştirir misiniz?"
        entity_types = {
            item.entity_type
            for item in result.entity_results
            if item.status
            in {
                DataResolutionStatus.NO_MATCH,
                DataResolutionStatus.NEEDS_CLARIFICATION,
            }
        } | set(result.missing_entities)
        if EntityType.PRODUCT in entity_types:
            return "Bahsettiğiniz ürünü bulamadım. Ürün adını biraz daha net yazar mısınız?"
        if EntityType.ORDER in entity_types:
            return "Bahsettiğiniz siparişi bulamadım. Sipariş numarasını paylaşır mısınız?"
        if EntityType.COUPON in entity_types:
            return "Bu kupon kodunu bulamadım. Kupon kodunu kontrol edip tekrar yazar mısınız?"
        return "İlgili kaydı doğrulayamadım. Hangi kayıt için işlem yapmak istediğinizi netleştirir misiniz?"

    @staticmethod
    def _resolved_order_no(result: DataResolverOutput) -> str | None:
        for item in result.entity_results:
            if (
                item.entity_type == EntityType.ORDER
                and item.status == DataResolutionStatus.RESOLVED
                and item.input_reference.type == "ORDER_NO"
            ):
                return str(item.input_reference.value)
        return None

    @staticmethod
    def _skipped_data_resolution() -> DataResolverOutput:
        return DataResolverOutput(
            status=DataResolutionStatus.SKIP,
            next_step=ResolutionNextStep.SKIP,
            warnings=["NOT_CALLED_CONTEXT_PLAN_TERMINAL"],
        )

    @staticmethod
    def _evidence_required_contexts(context_plan: ContextResolverOutput) -> list[dict]:
        fields = set(context_plan.fields)
        sources = set(context_plan.data_sources)
        purposes: list[str] = []
        if fields & {"capacity_ml", "volume_ml"}:
            purposes.append("PRODUCT_CAPACITY")
        if fields & {"price", "discounted_price", "currency"}:
            purposes.append("PRODUCT_PRICE")
        if fields & {"stock", "availability"}:
            purposes.append("PRODUCT_STOCK")
        if fields & {"rating_average", "review_count", "reviews"}:
            purposes.append("PRODUCT_REVIEWS")
        if fields & {"returnable", "return_policy_note"}:
            purposes.append("PRODUCT_RETURN_ELIGIBILITY")
        if "cancel_eligibility" in fields:
            purposes.append("ORDER_CANCEL_ELIGIBILITY")
        elif fields & {
            "estimated_delivery_at",
            "delay_reason",
            "tracking_number",
            "delivered_at",
        }:
            purposes.append("ORDER_SHIPPING_STATUS")
        elif fields & {"order_status", "shipping_status"}:
            purposes.append("ORDER_STATUS")
        if "payment_db" in sources:
            purposes.append(
                "PAYMENT_WITHOUT_ORDER"
                if "provider_reference" in fields
                else "PAYMENT_STATUS"
            )
        if "coupon_db" in sources:
            purposes.append(
                "COUPON_ELIGIBILITY"
                if fields & {"min_cart_total", "allowed_category", "cart_total"}
                else "COUPON_STATUS"
            )
        if "cart_db" in sources and "coupon_db" not in sources:
            purposes.append("CART_STATUS")
        if "return_db" in sources:
            purposes.append("RETURN_STATUS")
        return [{"purpose": purpose} for purpose in dict.fromkeys(purposes)]

    async def _last_customer_context(
        self, session: AsyncSession, conversation: Conversation
    ) -> dict:
        result = await session.scalar(
            select(RagRun.customer_context)
            .join(Message, Message.id == RagRun.assistant_message_id)
            .where(Message.conversation_id == conversation.id, Message.role == "ASSISTANT")
            .order_by(Message.id.desc())
            .limit(1)
        )
        return result or {}

    def _resolve_followup_reference(self, text: str, previous_context: dict) -> dict:
        if not self._is_contextual_followup(text, previous_context):
            return {}
        order_no = self._extract_order_no(text)
        category = previous_context.get("category") or "GENEL_DESTEK"
        if order_no:
            return {"order_no": order_no, "category": category, "is_followup": True}
        order_numbers = self._context_order_numbers(previous_context)
        ordinal = self._extract_ordinal_reference(text)
        if ordinal and order_numbers and ordinal <= len(order_numbers):
            return {
                "order_no": order_numbers[ordinal - 1],
                "category": category,
                "is_followup": True,
            }
        if len(order_numbers) == 1:
            return {
                "order_no": order_numbers[0],
                "category": category,
                "is_followup": True,
            }
        return {"category": category, "is_followup": True}

    async def _fallback_answer(
        self,
        session: AsyncSession,
        grouped: list[GroupedDocument],
        customer_context: dict | None = None,
        product_context: dict | None = None,
    ) -> str:
        customer_context = customer_context or {}
        product_context = product_context or {}
        decision_hints = [
            str(item).strip()
            for item in customer_context.get("decision_hints", [])
            if str(item).strip()
        ]
        decision_hints.extend(
            str(item).strip()
            for item in product_context.get("decision_hints", [])
            if str(item).strip()
        )
        customer_items = customer_context.get("items", [])
        formatted_items = [
            self._format_customer_context_item(item) for item in customer_items[:2]
        ]
        product_items = product_context.get("items", [])
        formatted_products = [
            self._format_product_context_item(item)
            for item in product_items[:2]
            if str(item).strip()
        ]
        route_mode = product_context.get("route_mode", "")
        product_match_reason = product_context.get("product_match_reason", "")
        if product_match_reason in {"ambiguous_catalog_match", "ambiguous_weak_match"}:
            names = [
                str(item.get("name", "")).strip()
                for item in product_context.get("top_candidates", [])[:3]
                if str(item.get("name", "")).strip()
            ]
            if len(names) >= 2:
                return f"{' mi, '.join(names)} mi? Hangi ürünü kastettiğinizi seçer misiniz?"
            return "Bu ürün için birden fazla benzer kayıt buldum. Ürün adını biraz daha net yazar mısınız?"
        if product_match_reason in {"no_catalog_match", "no_product_mention", "clarification_needed"} and route_mode == "product_only":
            return "Bu ürünle eşleşen net bir kayıt bulamadım. Ürün adını biraz daha açık yazar mısınız?"
        if formatted_products and (
            not route_mode or route_mode in {"product_only", "review_favorite_mixed"}
        ):
            return formatted_products[0]
        if decision_hints:
            lead = formatted_items[0] if formatted_items else "İlgili demo kayıt kontrol edildi."
            return f"{lead} {decision_hints[0]} İsterseniz bir sonraki adımı birlikte netleştirebiliriz."
        if not grouped:
            if customer_context.get("context_type") == "clarification_needed":
                return (
                    "Sorunuzla eşleşen net bir demo işlem seçemedim. Hangi sipariş, ödeme, iade veya kupon işlemi için destek istediğinizi biraz daha netleştirir misiniz?"
                )
            return (
                "Bu soru için yeterli doğrulanmış bilgi bulamadım. Sorunu biraz daha ayrıntılı yazabilir veya destek kaydı açabilirsiniz."
            )
        standard_chunk = await session.scalar(
            select(Chunk.content)
            .where(
                Chunk.doc_id == grouped[0].doc_id,
                Chunk.section == "standart_yanit",
            )
            .order_by(Chunk.chunk_id)
        )
        if standard_chunk:
            return f"{standard_chunk} Sorun hesabınızdaki özel bir işlemle ilgiliyse destek kaydı açabilirsiniz."
        document = await session.get(Document, grouped[0].doc_id)
        if document:
            standard = document.raw_json.get("standart_yanit", "")
            if standard and "?" not in standard:
                return f"{standard} Sorun devam ederse destek kaydı açabilirsiniz."
        return "İlgili destek dokümanı bulundu ancak otomatik cevap üretimi tamamlanamadı. Bu işlem için destek ekibinin kontrolü gerekebilir."

    def _format_customer_context_item(self, item: str) -> str:
        match = re.match(r"Sipariş\s+(DMO-[^:]+):\s*(.+)\.?$", item.strip())
        if match:
            order_no, detail_text = match.groups()
            details = self._parse_context_details(detail_text)
            pieces = [f"{order_no} numaralı sipariş"]
            if details.get("ürünler"):
                pieces.append(f"{details['ürünler']} ürünü için")
            sentence = " ".join(pieces)
            status_parts = []
            if details.get("kargo"):
                status_parts.append(f"kargo durumu {details['kargo']}")
            if details.get("sipariş durumu"):
                status_parts.append(f"sipariş durumu {details['sipariş durumu']}")
            if details.get("ödeme"):
                status_parts.append(f"ödeme durumu {details['ödeme']}")
            if status_parts:
                sentence += ". " + ", ".join(status_parts)
            if details.get("takip no"):
                sentence += f". Takip numarası: {details['takip no']}"
            if details.get("not"):
                sentence += f". Not: {details['not']}"
            return sentence + "."
        match = re.match(r"Ödeme kaydı\s+([^:]+):\s*(.+)\.?$", item.strip())
        if match:
            reference, detail_text = match.groups()
            details = self._parse_context_details(detail_text)
            linked = details.get("bağlantı", "")
            if "bağlı değil" in linked:
                sentence = f"{reference} referanslı ödeme siparişe bağlı görünmüyor"
            else:
                sentence = f"{reference} referanslı ödeme kaydı kontrol edildi"
            if details.get("durum"):
                sentence += f". Durumu: {details['durum']}"
            if details.get("tutar"):
                sentence += f". Tutar: {details['tutar']} TL"
            if details.get("açıklama") and details["açıklama"] != "None":
                sentence += f". Açıklama: {details['açıklama']}"
            return sentence + "."
        match = re.match(r"Aktif sepet:\s*(.+)\.?$", item.strip())
        if match:
            details = self._parse_context_details(match.group(1))
            product_text = details.get("ürünler") or "ürün görünmüyor"
            sentence = f"Aktif sepette {product_text} var"
            if details.get("kupon") and details["kupon"] != "yok":
                sentence += f". Girilen kupon: {details['kupon']}"
            if details.get("kupon durumu"):
                sentence += f". Kupon durumu: {details['kupon durumu']}"
            if details.get("toplam"):
                sentence += f". Sepet toplamı: {details['toplam']} TL"
            return sentence + "."
        return item

    def _parse_context_details(self, detail_text: str) -> dict[str, str]:
        details: dict[str, str] = {}
        for part in detail_text.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            details[key.strip()] = value.strip().rstrip(".")
        return details

    def _format_product_context_item(self, item: str) -> str:
        match = re.match(r"(.+?)\s+\(([^)]+)\);\s*(.+)$", item.strip())
        if not match:
            return item
        name, _, detail_text = match.groups()
        details = self._parse_context_details(detail_text)
        parts = [f"{name} için katalogdaki bilgileri kontrol ettim"]
        info: list[str] = []
        if details.get("açıklama"):
            info.append(details["açıklama"])
        if details.get("detay"):
            info.append(details["detay"])
        if details.get("fiyat"):
            info.append(f"fiyatı {details['fiyat'].replace('TRY', 'TL').strip()}")
        if details.get("stok"):
            info.append(f"stok durumu {details['stok']}")
        if details.get("puan"):
            info.append(f"ortalama puanı {details['puan']}")
        if details.get("iade edilebilir"):
            info.append(
                "iade edilebilir" if details["iade edilebilir"] == "evet" else "iade edilemez"
            )
        if details.get("garanti"):
            info.append(f"{details['garanti']} garanti süresi")
        if details.get("özellikler"):
            info.append(f"temel özellikleri {details['özellikler']}")
        if details.get("yorum özeti"):
            info.append(f"kullanıcı yorumlarında öne çıkanlar: {details['yorum özeti']}")
        if info:
            parts.append(", ".join(info))
        parts.append("Daha ayrıntılı teknik bilgi istersen devam edebilirim.")
        return ". ".join(parts)

    async def run(
        self,
        session: AsyncSession,
        conversation: Conversation,
        user: User,
        safe_query: str,
        ip_hash: str,
        frontend_context: dict | None = None,
    ) -> tuple[
        Message,
        str,
        list[GroupedDocument],
        list[tuple[object, float, int]],
        ClassificationResult,
    ]:
        started = time.perf_counter()
        frontend_context = frontend_context or {}
        masked_query, pii_findings = mask_pii(safe_query)
        previous_customer_context = await self._last_customer_context(session, conversation)
        followup_reference = self._resolve_followup_reference(
            masked_query, previous_customer_context
        )
        classification = await self.classifier.classify(safe_query, masked_query)
        classifier_usage = dict(self.classifier.last_usage)
        history_rows = (
            await session.execute(
                select(Message.role, Message.safe_content)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.id.desc())
                .limit(8)
            )
        ).all()
        history = [
            f"{role}: {content}" for role, content in reversed(history_rows)
        ]
        rewrite_usage: dict = {}
        pipeline_errors: list[str] = []
        if classification.expected_action == "REJECT":
            rewrite = {
                "canonical_query": masked_query,
                "category": classification.category,
                "is_in_scope": False,
            }
        else:
            try:
                rewrite = await self.rewriter.rewrite(
                    masked_query,
                    history,
                    use_dev_model=True,
                )
                rewrite_usage = dict(self.gemini.last_usage)
            except GeminiServiceError:
                pipeline_errors.append("GEMINI_REWRITE_UNAVAILABLE")
                rewrite = {
                    "canonical_query": masked_query,
                    "category": classification.category,
                    "is_in_scope": True,
                }
        canonical = rewrite.get("canonical_query", masked_query).strip() or masked_query
        category = classification.category
        if category == "GENEL_DESTEK" and rewrite.get("category"):
            category = rewrite.get("category", "GENEL_DESTEK")
        if followup_reference:
            if category == "GENEL_DESTEK":
                category = followup_reference["category"]
            canonical = (
                f"{followup_reference['order_no']} numaralı sipariş bağlamında: "
                f"{canonical}"
                if followup_reference.get("order_no")
                else f"{followup_reference['category']} bağlamında: {canonical}"
            )
            classification = replace(
                classification,
                category=category,
                expected_action="RAG_ANSWER",
                confidence=max(classification.confidence or 0, 0.75),
            )

        resolver_scope = bool(rewrite.get("is_in_scope", True)) and (
            classification.expected_action != "REJECT"
        )
        conversation_state = await self.product_context._load_state(
            session, conversation
        )
        context_plan = self.context_resolver.resolve(
            self._context_resolver_input(
                classification,
                masked_query,
                canonical_query=canonical,
                is_in_scope=resolver_scope,
                conversation_state=conversation_state,
                frontend_context=frontend_context,
                followup_reference=followup_reference,
            )
        )
        context_plan_metadata = self._context_plan_metadata(context_plan)
        resolver_fetches_context = (
            context_plan.next_step == "FETCH_CONTEXT"
            and not context_plan.needs_clarification
        )
        data_resolution = self._skipped_data_resolution()
        if resolver_fetches_context:
            data_resolver = self.data_resolver or DataResolver(
                SqlAlchemyDataResolverAdapter(session)
            )
            data_resolution = await data_resolver.resolve(
                self._data_resolver_input(
                    user_id=user.id,
                    message=masked_query,
                    context_plan=context_plan,
                    conversation_state=conversation_state,
                    frontend_context=frontend_context,
                )
            )
        data_resolution_metadata = data_resolution.model_dump(mode="json")
        data_allows_context = self._data_resolution_allows_context(data_resolution)
        pipeline_fetches_context = resolver_fetches_context and data_allows_context
        data_resolution_blocks_context = (
            resolver_fetches_context and not data_allows_context
        )
        evidence_output = EvidenceFetcherOutput()
        if pipeline_fetches_context and self.evidence_fetcher is not None:
            try:
                evidence_fetcher = self.evidence_fetcher
                adapter = getattr(evidence_fetcher, "adapter", None)
                if isinstance(adapter, SqlAlchemyEvidenceFetcherAdapter):
                    evidence_fetcher = EvidenceFetcher(
                        adapter.bind(session)
                    )
                evidence_output = await evidence_fetcher.fetch(
                    {
                        "user_id": user.id,
                        "context_plan": context_plan.model_dump(mode="json"),
                        "data_resolution": data_resolution.model_dump(mode="json"),
                        "required_contexts": self._evidence_required_contexts(
                            context_plan
                        ),
                    }
                )
            except Exception as exc:
                safe_error_summary = type(exc).__name__
                evidence_output.warnings.append(
                    f"EVIDENCE_FETCHER_ERROR:{safe_error_summary}"
                )
                pipeline_errors.append("EVIDENCE_FETCHER_ERROR")
        evidence_metadata = evidence_output.model_dump(mode="json")
        effective_frontend_context = dict(frontend_context)
        resolved_data_entities = data_resolution.resolved_entities
        if resolved_data_entities.product_id is not None:
            effective_frontend_context["current_product_id"] = (
                resolved_data_entities.product_id
            )
        if resolved_data_entities.order_id is not None:
            effective_frontend_context["current_order_id"] = (
                resolved_data_entities.order_id
            )
        if resolved_data_entities.cart_id is not None:
            effective_frontend_context["current_cart_id"] = resolved_data_entities.cart_id
        if resolved_data_entities.payment_id is not None:
            effective_frontend_context["current_payment_id"] = (
                resolved_data_entities.payment_id
            )
        selected_order_no = self._resolved_order_no(data_resolution) or (
            followup_reference.get("order_no")
        )
        explicit_coupon_resolution = (
            context_plan.resolved_entities.coupon_code is not None
            and resolved_data_entities.coupon_id is not None
        )
        legacy_context_allowed = (
            pipeline_fetches_context and not explicit_coupon_resolution
        )

        user_message = Message(
            conversation_id=conversation.id,
            role="USER",
            safe_content=masked_query,
            canonical_query=canonical,
            category=category,
            ip_hash=ip_hash,
            security_metadata={
                "pii_masked": pii_findings,
                "classification": classification.as_dict(),
                "context_resolver": context_plan_metadata,
                "data_resolver": data_resolution_metadata,
                "evidence_fetcher": evidence_metadata,
            },
        )
        session.add(user_message)
        await session.flush()

        support_in_scope = resolver_scope and pipeline_fetches_context
        product_context = (
            await self.product_context.build(
                session,
                user,
                category,
                canonical,
                conversation=conversation,
                selected_order_no=selected_order_no,
                frontend_context=effective_frontend_context,
                original_query=safe_query,
            )
            if legacy_context_allowed
            else {
                "route_mode": (
                    "data_resolver_coupon_only"
                    if explicit_coupon_resolution
                    else "resolver_no_fetch"
                ),
                "category": category,
                "context_type": "clarification_needed",
                "items": [],
                "text": "",
                "decision_hints": [],
            }
        )
        route_mode = product_context.get("route_mode", "support_only")
        product_in_scope = (
            pipeline_fetches_context and route_mode != "fallback_unclear"
        )
        support_context = (
            await self.customer_context.build(
                session,
                user,
                category,
                canonical,
                selected_order_no=selected_order_no,
                selected_order_id=resolved_data_entities.order_id,
            )
            if legacy_context_allowed
            and support_in_scope
            and route_mode != "product_only"
            else {"category": category, "items": [], "text": ""}
        )
        in_scope = pipeline_fetches_context and (support_in_scope or product_in_scope)
        debug_metadata = {
            "route_mode": route_mode,
            "context_resolver": context_plan_metadata,
            "data_resolver": data_resolution_metadata,
            "evidence_fetcher": evidence_metadata,
            "warnings": list(evidence_output.warnings),
            "classification": {
                "category": classification.category,
                "subcategory": classification.subcategory,
                "expected_action": classification.expected_action,
                "confidence": classification.confidence,
            },
            "canonical_query": canonical,
            "followup_reference": followup_reference,
            "frontend_context": {
                key: value
                for key, value in frontend_context.items()
                if key
                in {
                    "current_product_id",
                    "current_order_id",
                    "current_cart_id",
                    "current_return_id",
                    "current_payment_id",
                    "page_context",
                }
            },
            "customer_context": {
                "category": support_context.get("category"),
                "intent": support_context.get("intent"),
                "context_type": support_context.get("context_type"),
                "selected_counts": support_context.get("selected_counts", {}),
                "item_count": len(support_context.get("items", [])),
                "decision_hint_count": len(support_context.get("decision_hints", [])),
            },
            "product_context": {
                "route_mode": route_mode,
                "context_type": product_context.get("context_type"),
                "product_match_reason": product_context.get("product_match_reason", ""),
                "product_match_score": product_context.get("product_match_score", 0),
                "explicit_product_mention": product_context.get("explicit_product_mention", False),
                "top_candidates": product_context.get("top_candidates", []),
                "selected_counts": product_context.get("selected_counts", {}),
                "item_count": len(product_context.get("items", [])),
                "decision_hint_count": len(product_context.get("decision_hints", [])),
                "selected_product_ids": product_context.get("selected_product_ids", []),
                "selected_order_ids": product_context.get("selected_order_ids", []),
                "selected_return_ids": product_context.get("selected_return_ids", []),
                "selected_payment_ids": product_context.get("selected_payment_ids", []),
            },
            "gemini_enabled": self.gemini.enabled,
            "gemini_model": self.gemini.model_name(use_dev_model=True),
            "gemini_called": False,
            "gemini_error": "",
            "gemini_answer_length": 0,
            "retrieved_doc_ids": [],
            "raw_cited_doc_ids": [],
            "normalized_cited_doc_ids": [],
            "invalid_cited_doc_ids": [],
            "citation_normalized": False,
            "cited_doc_ids": [],
            "guard_reason": "",
            "fallback_reason": "",
            "formatter_mode": "",
            "support_rag_used": False,
            "product_context_used": False,
            "customer_context_used": False,
        }
        grouped = []
        should_run_support_rag = self._should_run_support_rag(
            needs_support_rag=context_plan.needs_support_rag,
            support_in_scope=support_in_scope,
            route_mode=route_mode,
        )
        if should_run_support_rag:
            try:
                grouped = await self.retrieval.grouped_search(
                    session,
                    canonical,
                    candidate_limit=30,
                    max_documents=2,
                    max_sections=5,
                )
            except HTTPException:
                pipeline_errors.append("RETRIEVAL_UNAVAILABLE")
        if should_run_support_rag and not grouped and support_context.get("text"):
            try:
                grouped = await self.retrieval.grouped_by_category(
                    session,
                    category,
                    max_documents=2,
                    max_sections=5,
                )
            except HTTPException:
                pipeline_errors.append("CATEGORY_RETRIEVAL_UNAVAILABLE")
        grouped, reranker_score = await self.reranker.rerank(canonical, grouped)
        if grouped and category == "GENEL_DESTEK":
            category = grouped[0].category
            user_message.category = category
        debug_metadata["retrieved_doc_ids"] = [
            {"doc_id": item.doc_id, "score": item.best_score} for item in grouped
        ]
        debug_metadata["support_rag_used"] = bool(grouped)
        debug_metadata["product_context_used"] = bool(product_context.get("text"))
        debug_metadata["customer_context_used"] = bool(support_context.get("text"))

        similar = (
            await self.similar.search(session, canonical, category, limit=3)
            if support_in_scope
            else []
        )
        few_shots = [
            {
                "question": solution.canonical_question,
                "answer": solution.safe_answer,
                "success_rate": solution.success_rate,
            }
            for solution, _, views in similar[:2]
            if views >= self.settings.similar_solution_min_views
        ]
        llm_context = self.context_builder.build(grouped)
        available_sources = [
            {"doc_id": item.doc_id, "title": item.title} for item in grouped
        ]
        generated = {"answer": "", "cited_doc_ids": []}
        answer_usage: dict = {}
        evidence_sections = (
            "product_evidence",
            "order_evidence",
            "payment_evidence",
            "coupon_evidence",
            "cart_evidence",
            "return_evidence",
            "review_evidence",
            "missing_evidence",
        )
        has_evidence_context = any(
            evidence_metadata.get(section) for section in evidence_sections
        )
        answer_scope = {
            "evidence_only": True,
            "requested_purposes": [
                item["purpose"]
                for item in self._evidence_required_contexts(context_plan)
            ],
            "allowed_entity_ids": {
                key: value
                for key, value in resolved_data_entities.model_dump(
                    mode="json"
                ).items()
                if value is not None
            },
            "actions_performed": False,
        }
        if in_scope and (
            grouped
            or support_context.get("text")
            or product_context.get("text")
            or has_evidence_context
        ):
            try:
                debug_metadata["gemini_called"] = self.gemini.enabled
                generated = await self.gemini.answer(
                    canonical,
                    history,
                    support_context.get("text", ""),
                    product_context.get("text", ""),
                    llm_context,
                    few_shots,
                    available_sources,
                    original_user_message=masked_query,
                    resolved_entities=resolved_data_entities.model_dump(mode="json"),
                    evidence_pack=evidence_metadata,
                    answer_scope=answer_scope,
                    use_dev_model=True,
                )
                answer_usage = dict(self.gemini.last_usage)
            except GeminiServiceError:
                pipeline_errors.append("GEMINI_ANSWER_UNAVAILABLE")
                debug_metadata["gemini_error"] = "GeminiServiceError"
        elif not in_scope:
            debug_metadata["fallback_reason"] = "out_of_scope"
        else:
            debug_metadata["fallback_reason"] = "no_context"
        raw_citations = [
            str(item).strip()
            for item in generated.get("cited_doc_ids", [])
            if str(item).strip()
        ]
        normalized_citations, invalid_citations, citation_normalized = (
            self._normalize_citations(raw_citations, available_sources)
        )
        cited_ids = set(normalized_citations)
        debug_metadata["raw_cited_doc_ids"] = raw_citations
        debug_metadata["normalized_cited_doc_ids"] = normalized_citations
        debug_metadata["invalid_cited_doc_ids"] = invalid_citations
        debug_metadata["citation_normalized"] = citation_normalized
        debug_metadata["cited_doc_ids"] = normalized_citations
        debug_metadata["gemini_answer_length"] = len(generated.get("answer", ""))
        allowed_ids = {item.doc_id for item in grouped}
        answer = guard_llm_output(
            generated.get("answer", ""),
            allowed_ids,
        )
        if generated.get("answer") and not answer:
            debug_metadata["guard_reason"] = "guard_rejected"
        elif not generated.get("answer") and in_scope:
            debug_metadata["guard_reason"] = "empty_answer"
        if invalid_citations or (cited_ids and not cited_ids.issubset(allowed_ids)):
            answer = ""
            debug_metadata["guard_reason"] = "invalid_citation"
        has_answer_context = bool(
            grouped
            or support_context.get("text")
            or product_context.get("text")
            or has_evidence_context
        )
        if data_resolution_blocks_context:
            answer = self._data_resolution_clarification_message(data_resolution)
            debug_metadata["fallback_reason"] = (
                f"data_resolver_{data_resolution.status.value.casefold()}"
            )
            debug_metadata["formatter_mode"] = "data_resolver_clarification"
        elif context_plan.next_step == "CLARIFY" or context_plan.needs_clarification:
            answer = self._resolver_clarification_message(
                context_plan.clarification_reason
            )
            debug_metadata["fallback_reason"] = (
                context_plan.clarification_reason or "context_resolver_clarification"
            )
            debug_metadata["formatter_mode"] = "resolver_clarification"
        elif context_plan.next_step == "FALLBACK":
            if context_plan.fallback_reason == "UNCLEAR_INTENT":
                answer = self._resolver_clarification_message(None)
                debug_metadata["formatter_mode"] = "resolver_clarification"
            else:
                answer = "Bu asistan yalnızca e-ticaret müşteri destek konularını yanıtlar."
                debug_metadata["formatter_mode"] = "out_of_scope_plain"
            debug_metadata["fallback_reason"] = (
                context_plan.fallback_reason or "context_resolver_fallback"
            )
        elif classification.expected_action == "ASK_CLARIFICATION" and not has_answer_context:
            answer = (
                "Sorununuzu doğru yönlendirebilmem için hangi sipariş, ödeme, "
                "iade veya teslimat durumuyla ilgili olduğunu biraz daha açıklar mısınız?"
            )
            debug_metadata["fallback_reason"] = "ask_clarification"
            debug_metadata["formatter_mode"] = "clarification_natural"
        elif not in_scope:
            answer = "Bu asistan yalnızca e-ticaret müşteri destek konularını yanıtlar."
            debug_metadata["formatter_mode"] = "out_of_scope_plain"
        elif not answer:
            if not debug_metadata["fallback_reason"]:
                if debug_metadata["gemini_error"]:
                    debug_metadata["fallback_reason"] = "gemini_error"
                elif not self.gemini.enabled:
                    debug_metadata["fallback_reason"] = "gemini_disabled"
                elif debug_metadata["guard_reason"]:
                    debug_metadata["fallback_reason"] = debug_metadata["guard_reason"]
                else:
                    debug_metadata["fallback_reason"] = "empty_answer"
            answer = await self._fallback_answer(
                session, grouped, support_context, product_context
            )
            debug_metadata["formatter_mode"] = "fallback_natural"
        else:
            debug_metadata["formatter_mode"] = "gemini_natural"
        payment_items = [str(item) for item in product_context.get("payment_items", [])]
        no_order_payment_item = next(
            (
                item
                for item in payment_items
                if "CAPTURED_NO_ORDER" in item and "siparişe bağlı değil" in item
            ),
            "",
        )
        if no_order_payment_item:
            payment_summary = self._format_customer_context_item(
                no_order_payment_item
            )
            answer = (
                f"{payment_summary} Bu durumda ödeme başarılı alınmış görünüyor ancak "
                "sipariş kaydı oluşmamış. Tekrar ödeme denemeden önce ödeme/sipariş "
                "eşleştirmesi için destek kaydı açılması veya ödeme incelemesi "
                "başlatılması gerekir."
            )
            debug_metadata["formatter_mode"] = "payment_no_order_context"
        answer, output_pii = mask_pii(answer)

        top_score = grouped[0].best_score if grouped else 0.0
        combined_score = composite_confidence(
            top_score, reranker_score, classification.confidence
        )
        assistant = Message(
            conversation_id=conversation.id,
            role="ASSISTANT",
            safe_content=answer,
            category=category,
            confidence=confidence_label(combined_score, self.settings),
            confidence_score=combined_score,
            sources=[
                {
                    "doc_id": item.doc_id,
                    "title": item.title,
                    "category": item.category,
                    "subcategory": item.subcategory,
                    "best_score": item.best_score,
                    "matched_sections": item.matched_sections,
                    "combined_context": item.combined_context,
                }
                for item in grouped
            ],
            ip_hash=ip_hash,
            security_metadata={
                "output_pii_masked": output_pii,
                "pipeline_errors": pipeline_errors,
                "debug": debug_metadata,
            },
        )
        session.add(assistant)
        await session.flush()
        await self.similar.record_impressions(
            session, similar, assistant.id, conversation.user_id
        )
        prompt_tokens = (
            classifier_usage.get("promptTokenCount", 0)
            +
            rewrite_usage.get("promptTokenCount", 0)
            + answer_usage.get("promptTokenCount", 0)
        ) or None
        completion_tokens = (
            classifier_usage.get("candidatesTokenCount", 0)
            +
            rewrite_usage.get("candidatesTokenCount", 0)
            + answer_usage.get("candidatesTokenCount", 0)
        ) or None
        total_tokens = (
            classifier_usage.get("totalTokenCount", 0)
            +
            rewrite_usage.get("totalTokenCount", 0)
            + answer_usage.get("totalTokenCount", 0)
        ) or None
        estimated_cost = None
        if (
            prompt_tokens is not None
            and completion_tokens is not None
            and self.settings.gemini_prompt_cost_per_million is not None
            and self.settings.gemini_completion_cost_per_million is not None
        ):
            estimated_cost = Decimal(
                str(
                    prompt_tokens
                    * self.settings.gemini_prompt_cost_per_million
                    / 1_000_000
                    + completion_tokens
                    * self.settings.gemini_completion_cost_per_million
                    / 1_000_000
                )
            )
        await self.product_context.update_state(
            session,
            conversation,
            last_topic=category,
            last_product_id=product_context.get("primary_product", {}).get("id"),
            last_product_name=product_context.get("primary_product", {}).get("name", ""),
            last_order_id=product_context.get("primary_order", {}).get("id"),
            last_order_no=product_context.get("primary_order", {}).get("order_no", ""),
            last_return_id=product_context.get("primary_return", {}).get("id"),
            last_cart_id=product_context.get("primary_cart", {}).get("id")
            or frontend_context.get("current_cart_id"),
            last_payment_id=product_context.get("primary_payment", {}).get("id")
            or frontend_context.get("current_payment_id"),
            last_intent=product_context.get("route_mode", ""),
            last_action=(
                "show_technical_details"
                if product_context.get("primary_product")
                else classification.expected_action
            ),
            last_suggested_action=(
                "show_product_details" if product_context.get("primary_product") else ""
            ),
            last_mentioned_product_ids=product_context.get("selected_product_ids", []),
            last_mentioned_order_ids=product_context.get("selected_order_ids", []),
            state_metadata={
                "route_mode": product_context.get("route_mode", ""),
                "support_category": category,
                "last_recommended_action": (
                    "show_product_details"
                    if product_context.get("primary_product")
                    else ""
                ),
                "fallback_reason": debug_metadata["fallback_reason"],
            },
        )
        session.add(
            RagRun(
                assistant_message_id=assistant.id,
                rewritten_query=canonical,
                retrieval_results=assistant.sources,
                customer_context={
                    "support": support_context,
                    "product": product_context,
                },
                few_shot_examples=few_shots,
                model_name=(
                    self.settings.gemini_model_dev
                    if self.gemini.enabled
                    else "fallback"
                ),
                latency_ms=int((time.perf_counter() - started) * 1000),
                token_usage={
                    "classifier": classifier_usage,
                    "rewrite": rewrite_usage,
                    "answer": answer_usage,
                },
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                retrieval_score=top_score,
                reranker_score=reranker_score,
                classifier_confidence=classification.confidence,
                composite_confidence=combined_score,
                classification_result={
                    **classification.as_dict(),
                    "context_resolver": context_plan_metadata,
                    "data_resolver": data_resolution_metadata,
                    "evidence_fetcher": evidence_metadata,
                },
            )
        )
        if conversation.title == "Yeni görüşme":
            conversation.title = canonical[:255]
        await session.commit()
        await session.refresh(assistant)
        return assistant, canonical, grouped, similar, classification
