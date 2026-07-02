from __future__ import annotations

import asyncio
import copy
import logging
import time
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

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
from ..schemas.evidence_fetcher import (
    EvidenceEntityType,
    EvidenceFetcherOutput,
    EvidenceItem,
    EvidenceProvenance,
    EvidencePurpose,
)
from .gemini import GeminiService, GeminiServiceError, guard_llm_output
from .ai_contracts import ContextBuilder, PassthroughReranker
from .classifier import ClassificationResult, ClassifierService
from .commerce_answer import build_deterministic_answer
from .compact_context import build_compact_context, compact_policy_text
from .confidence import composite_confidence, confidence_label
from .context_resolver import ContextResolver
from .data_resolver import DataResolver, SqlAlchemyDataResolverAdapter
from .evidence_fetcher import EvidenceFetcher, SqlAlchemyEvidenceFetcherAdapter
from .demo_commerce import CustomerContextService
from .product_context import ProductContextService
from .privacy import mask_pii
from .pipeline_trace import PipelineTrace
from .retrieval import GroupedDocument, RetrievalService
from .similar import SimilarSolutionService


logger = logging.getLogger(__name__)
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
USER_ORDER_CONTEXT_INTENTS = {
    "CREATE_RETURN_REQUEST",
    "RETURN_CREATE",
    "ORDER_CANCELLATION",
    "ORDER_CANCEL",
    "RETURN_STATUS",
    "ORDER_STATUS",
    "SHIPPING_DELIVERY",
    "ORDER_SHIPPING_DELAY",
    "MARKED_DELIVERED_NOT_RECEIVED",
    "DELIVERED_NOT_RECEIVED",
}


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
        self.last_stage = "idle"
        self.last_timeout_state: dict[str, object] = {}
        self.current_trace_id = ""

    @staticmethod
    def _stage_timeout(stage: str, default_seconds: float) -> float:
        if stage in {
            "product_context",
            "customer_context",
            "data_resolver",
            "evidence_fetcher",
            "retrieval",
            "similar",
        }:
            return min(default_seconds, 12.0)
        if stage in {"rewrite", "gemini_answer"}:
            return min(default_seconds, 60.0)
        return default_seconds

    @staticmethod
    def _json_safe(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: SupportPipeline._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [SupportPipeline._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [SupportPipeline._json_safe(item) for item in value]
        return value

    def _log_stage(self, stage: str, started: float, status: str, detail: str = "") -> None:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "pipeline_stage trace_id=%s stage=%s status=%s ms=%s detail=%s",
            getattr(self, "current_trace_id", ""),
            stage,
            status,
            elapsed_ms,
            detail,
        )

    def _remember_timeout_state(self, **kwargs: object) -> None:
        self.last_timeout_state.update(kwargs)

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
        intent = (classification.intent or "").strip().upper() or self._infer_context_intent(
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
                "requested_information": classification.requested_information,
                "expected_action": classification.expected_action,
                "priority": classification.priority,
                "routing_hints": classification.routing_hints,
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
    def _user_order_context_resolution() -> DataResolverOutput:
        return DataResolverOutput(
            status=DataResolutionStatus.PARTIALLY_RESOLVED,
            next_step=ResolutionNextStep.FETCH_EVIDENCE,
            warnings=["USER_ORDER_CONTEXT_LOOKUP"],
        )

    @staticmethod
    def _needs_user_order_context(
        classification: ClassificationResult,
        context_plan: ContextResolverOutput,
    ) -> bool:
        signals = {
            str(classification.intent or "").strip().upper(),
            str(classification.expected_action or "").strip().upper(),
            str(classification.subcategory or "").strip().upper(),
        }
        if signals & USER_ORDER_CONTEXT_INTENTS:
            return True
        sources = set(context_plan.data_sources)
        return bool(
            sources & {"order_db", "shipment_db", "return_db", "payment_db"}
            and str(classification.category or "").strip().upper()
            in {"IADE", "SIPARIS", "KARGO_TESLIMAT", "ODEME"}
        )

    @staticmethod
    def _is_generic_policy_question(
        classification: ClassificationResult,
        context_plan: ContextResolverOutput,
        query: str,
        frontend_context: dict,
    ) -> bool:
        entities = context_plan.resolved_entities
        if any(
            value is not None
            for value in (
                entities.order_no,
                entities.order_id,
                entities.product_id,
                entities.product_name,
                getattr(entities, "payment_id", None),
                getattr(entities, "return_id", None),
            )
        ):
            return False
        if any(
            frontend_context.get(key)
            for key in ("current_product_id", "current_order_id", "current_return_id", "current_payment_id")
        ):
            return False
        normalized = SupportPipeline._normalize_match_text(query)
        personal_terms = {
            "benim",
            "siparisim",
            "siparisimi",
            "kargom",
            "odemem",
            "iadem",
            "siparişim",
            "siparişimi",
            "ödemem",
        }
        if any(term in normalized for term in personal_terms):
            return False
        procedure_terms = {"nasil", "nasıl", "olustur", "oluştur", "baslat", "başlat"}
        category = str(classification.category or "").strip().upper()
        return (
            category in {"IADE", "SIPARIS", "KARGO_TESLIMAT", "ODEME", "GENEL_DESTEK"}
            and any(term in normalized for term in procedure_terms)
        )

    @staticmethod
    def _planning_result(
        classification: ClassificationResult,
        context_plan: ContextResolverOutput,
        *,
        query: str,
        frontend_context: dict,
        route_family: str,
        generic_policy_question: bool,
        followup_catalog_question: bool,
    ) -> dict:
        entities = context_plan.resolved_entities.model_dump(mode="json")
        sources = set(context_plan.data_sources)
        current_product_id = frontend_context.get("current_product_id")
        has_order_reference = bool(entities.get("order_no") or entities.get("order_id"))
        explicit_product_mention = bool(
            entities.get("product_id")
            or (entities.get("product_name") and not has_order_reference)
            or current_product_id
        )
        should_use_order_db = bool(
            not generic_policy_question
            and (
                "order_db" in sources
                or entities.get("order_no")
                or entities.get("order_id")
                or frontend_context.get("current_order_id")
            )
        )
        should_use_product_db = bool(
            not generic_policy_question
            and (
                "product_db" in sources
                or route_family in {"PRODUCT", "MIXED"}
                or current_product_id
                or explicit_product_mention
                or followup_catalog_question
            )
        )
        return {
            "domain": classification.domain,
            "intent": classification.intent,
            "entities": {
                "order_no": entities.get("order_no"),
                "explicit_product_mention": explicit_product_mention,
                "current_product_id": current_product_id,
            },
            "required_data": context_plan.fields,
            "should_use_rag": bool(context_plan.needs_support_rag or generic_policy_question),
            "should_use_order_db": should_use_order_db,
            "should_use_product_db": should_use_product_db,
            "should_use_return_db": bool(not generic_policy_question and "return_db" in sources),
            "should_use_payment_db": bool(not generic_policy_question and "payment_db" in sources),
            "should_use_product_fuzzy": bool(
                should_use_product_db
                and explicit_product_mention
                and not current_product_id
                and not has_order_reference
            ),
            "generic_policy_question": generic_policy_question,
        }

    @staticmethod
    def _canonical_product_from_order_evidence(
        evidence_output: EvidenceFetcherOutput,
    ) -> int | None:
        for item in evidence_output.order_evidence:
            data = item.data or {}
            for order_item in data.get("order_items") or []:
                product_id = SupportPipeline._safe_int(order_item.get("product_id"))
                if product_id is not None:
                    return product_id
        return None

    @staticmethod
    def _merge_evidence_output(
        target: EvidenceFetcherOutput, source: EvidenceFetcherOutput
    ) -> EvidenceFetcherOutput:
        for field in (
            "product_evidence",
            "order_evidence",
            "shipment_evidence",
            "payment_evidence",
            "coupon_evidence",
            "cart_evidence",
            "return_evidence",
            "review_evidence",
            "missing_evidence",
            "warnings",
        ):
            getattr(target, field).extend(getattr(source, field))
        return target

    @staticmethod
    def _merge_product_context_evidence(
        target: EvidenceFetcherOutput,
        product_context: dict,
    ) -> EvidenceFetcherOutput:
        existing_product_ids = {
            item.entity_id for item in target.product_evidence
        }
        for item in product_context.get("product_evidence") or []:
            product_id = SupportPipeline._safe_int(item.get("product_id"))
            data = item.get("data") or {}
            if product_id is None or product_id in existing_product_ids:
                continue
            target.product_evidence.append(
                EvidenceItem(
                    source="PRODUCT_CONTEXT_RESOLVER",
                    entity_type=EvidenceEntityType.PRODUCT,
                    entity_id=product_id,
                    purpose=EvidencePurpose.PRODUCT_PROFILE,
                    data=data,
                    provenance=EvidenceProvenance(
                        source="PRODUCT_CONTEXT_RESOLVER",
                        record_id=product_id,
                    ),
                )
            )
            existing_product_ids.add(product_id)

        existing_review_ids = {item.entity_id for item in target.review_evidence}
        for item in product_context.get("review_evidence") or []:
            product_id = SupportPipeline._safe_int(item.get("product_id"))
            data = item.get("data") or {}
            if product_id is None or product_id in existing_review_ids:
                continue
            target.review_evidence.append(
                EvidenceItem(
                    source="PRODUCT_CONTEXT_RESOLVER",
                    entity_type=EvidenceEntityType.REVIEW,
                    entity_id=product_id,
                    purpose=EvidencePurpose.PRODUCT_REVIEWS,
                    data=data,
                    provenance=EvidenceProvenance(
                        source="PRODUCT_CONTEXT_RESOLVER",
                        record_id=product_id,
                    ),
                )
            )
            existing_review_ids.add(product_id)
        return target

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
        if "product_db" in sources:
            purposes.append("PRODUCT_PROFILE")
        return [{"purpose": purpose} for purpose in dict.fromkeys(purposes)]

    @staticmethod
    def _planned_required_contexts(
        required_contexts: list[dict],
        planning_result: dict,
        context_plan: ContextResolverOutput,
    ) -> list[dict]:
        entities = context_plan.resolved_entities
        filtered: list[dict] = []
        for item in required_contexts:
            purpose = str(item.get("purpose") or "").upper()
            if purpose.startswith("PRODUCT_") and not (
                planning_result.get("should_use_product_fuzzy")
                or planning_result.get("entities", {}).get("current_product_id")
                or entities.product_id is not None
            ):
                continue
            if purpose == "RETURN_STATUS" and getattr(entities, "return_id", None) is None:
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _router_payload(classification: ClassificationResult) -> dict:
        payload = classification.raw_router_output or classification.as_dict()
        payload.setdefault("domain", classification.domain)
        payload.setdefault("intent", classification.intent)
        payload.setdefault("category", classification.category)
        payload.setdefault("subcategory", classification.subcategory)
        payload.setdefault("requested_information", classification.requested_information)
        payload.setdefault("requested_info", classification.requested_info)
        payload.setdefault("routing_hints", classification.routing_hints)
        payload.setdefault("expected_action", classification.expected_action)
        payload.setdefault("priority", classification.priority)
        return payload

    @staticmethod
    def _evidence_source_type(section: str) -> str:
        return {
            "product_evidence": "product",
            "order_evidence": "order",
            "shipment_evidence": "shipment",
            "payment_evidence": "payment",
            "coupon_evidence": "coupon",
            "cart_evidence": "cart",
            "return_evidence": "return_request",
            "review_evidence": "review",
        }.get(section, "rag")

    def _structured_evidence_pack(
        self,
        *,
        classification: ClassificationResult,
        context_plan: ContextResolverOutput,
        data_resolution: DataResolverOutput,
        evidence_output: EvidenceFetcherOutput,
        grouped: list[GroupedDocument],
        route_family: str,
    ) -> dict:
        db_evidence: list[dict] = []
        for section in (
            "product_evidence",
            "order_evidence",
            "shipment_evidence",
            "payment_evidence",
            "coupon_evidence",
            "cart_evidence",
            "return_evidence",
            "review_evidence",
        ):
            for item in getattr(evidence_output, section, []) or []:
                db_evidence.append(
                    {
                        "source_type": self._evidence_source_type(section),
                        "source_id": item.entity_id,
                        "title_or_name": item.data.get("name")
                        or item.data.get("order_no")
                        or item.data.get("code")
                        or item.data.get("provider_reference")
                        or item.data.get("return_code")
                        or item.data.get("status")
                        or "",
                        "matched_fields": [
                            key for key, value in item.data.items() if value is not None
                        ],
                        "structured_fields": item.data,
                        "raw_excerpt": ", ".join(
                            f"{key}={value}"
                            for key, value in list(item.data.items())[:6]
                            if value is not None
                        ),
                        "confidence": 1.0,
                        "retrieval_reason": item.purpose.value,
                        "provenance": item.provenance.model_dump(mode="json"),
                    }
                )
        rag_evidence = [
            {
                "source_type": "rag",
                "source_id": item.doc_id,
                "title_or_name": item.title,
                "matched_fields": item.matched_sections,
                "structured_fields": {},
                "raw_excerpt": item.combined_context[:800],
                "confidence": item.best_score,
                "retrieval_reason": "support_rag",
            }
            for item in grouped
        ]
        return {
            "router": self._router_payload(classification),
            "db_evidence": db_evidence,
            "rag_evidence": rag_evidence,
            "product_evidence": evidence_output.product_evidence and [
                item.model_dump(mode="json") for item in evidence_output.product_evidence
            ]
            or [],
            "order_evidence": evidence_output.order_evidence and [
                item.model_dump(mode="json") for item in evidence_output.order_evidence
            ]
            or [],
            "shipment_evidence": evidence_output.shipment_evidence and [
                item.model_dump(mode="json") for item in evidence_output.shipment_evidence
            ]
            or [],
            "payment_evidence": evidence_output.payment_evidence and [
                item.model_dump(mode="json") for item in evidence_output.payment_evidence
            ]
            or [],
            "coupon_evidence": evidence_output.coupon_evidence and [
                item.model_dump(mode="json") for item in evidence_output.coupon_evidence
            ]
            or [],
            "cart_evidence": evidence_output.cart_evidence and [
                item.model_dump(mode="json") for item in evidence_output.cart_evidence
            ]
            or [],
            "return_evidence": evidence_output.return_evidence and [
                item.model_dump(mode="json") for item in evidence_output.return_evidence
            ]
            or [],
            "review_evidence": evidence_output.review_evidence and [
                item.model_dump(mode="json") for item in evidence_output.review_evidence
            ]
            or [],
            "missing_evidence": [
                item.model_dump(mode="json") for item in evidence_output.missing_evidence
            ],
            "warnings": list(evidence_output.warnings),
            "retrieval_meta": {
                "route_family": route_family,
                "category": classification.category,
                "subcategory": classification.subcategory,
                "domain": classification.domain,
                "intent": classification.intent,
                "requested_information": classification.requested_information,
                "db_needed": bool(context_plan.data_sources),
                "rag_needed": context_plan.needs_support_rag,
            },
            "selected_evidence_count": len(db_evidence) + len(rag_evidence),
        }

    @staticmethod
    def _normalize_match_text(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value or "").casefold())
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^\w\s]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _product_identity(cls, evidence_pack: dict) -> dict:
        merged: dict = {}
        product_id = None
        for item in evidence_pack.get("product_evidence") or []:
            if product_id is None:
                product_id = item.get("source_id") or item.get("entity_id")
            data = item.get("data") or {}
            for key, value in data.items():
                if value not in (None, "", [], {}):
                    merged[key] = value
        return {
            "product_id": product_id,
            "product_name": merged.get("name") or "",
            "normalized_name": cls._normalize_match_text(merged.get("name") or ""),
        }

    @staticmethod
    def _is_product_specific_filter_needed(
        classification: ClassificationResult, evidence_pack: dict
    ) -> bool:
        if not evidence_pack.get("product_evidence"):
            return False
        domain = str(classification.domain or "").strip().upper()
        intent = str(classification.intent or "").strip().upper()
        category = str(classification.category or "").strip().upper()
        product_routing = domain in {"PRODUCT", "MIXED"} or intent.startswith("PRODUCT_")
        if not product_routing:
            return False
        if domain != "MIXED" and intent in {
            "RETURN_CREATE",
            "CREATE_RETURN_REQUEST",
            "ORDER_CANCEL",
            "ORDER_CANCELLATION",
            "ORDER_STATUS",
            "SHIPPING_DELIVERY",
            "MARKED_DELIVERED_NOT_RECEIVED",
            "DELIVERED_NOT_RECEIVED",
        }:
            return False
        if category in {"SIPARIS", "KARGO_TESLIMAT"} and domain != "MIXED":
            return False
        return True

    @classmethod
    def _order_product_match_reason(cls, order_item: dict, product: dict) -> str:
        product_id = product.get("product_id")
        item_product_id = order_item.get("product_id")
        if product_id is not None and item_product_id is not None:
            try:
                if int(product_id) == int(item_product_id):
                    return "product_id"
            except (TypeError, ValueError):
                pass
            return ""
        product_name = product.get("normalized_name") or ""
        item_name = cls._normalize_match_text(order_item.get("product_name") or "")
        if not product_name or not item_name:
            return ""
        if product_name == item_name or product_name in item_name or item_name in product_name:
            return "product_name_exact"
        product_tokens = {
            token for token in product_name.split() if len(token) > 2 and not token.isdigit()
        }
        item_tokens = {
            token for token in item_name.split() if len(token) > 2 and not token.isdigit()
        }
        if product_tokens and len(product_tokens & item_tokens) >= min(2, len(product_tokens)):
            return "product_name_token"
        return ""

    @classmethod
    def _filter_product_related_user_evidence(
        cls, evidence_pack: dict, classification: ClassificationResult
    ) -> tuple[dict, dict]:
        raw_counts = {
            key: len(evidence_pack.get(key) or [])
            for key in ("order_evidence", "shipment_evidence", "return_evidence", "payment_evidence")
        }
        if not cls._is_product_specific_filter_needed(classification, evidence_pack):
            trace = {
                "enabled": False,
                "raw_count": raw_counts,
                "selected_count": raw_counts,
                "dropped_count": {key: 0 for key in raw_counts},
                "selected_orders": [],
                "dropped_orders": [],
                "match_reason": "not_product_specific",
            }
            return evidence_pack, trace

        filtered = copy.deepcopy(evidence_pack)
        product = cls._product_identity(evidence_pack)
        selected_order_ids: set[int] = set()
        selected_order_nos: set[str] = set()
        selected_orders: list[dict] = []
        dropped_orders: list[dict] = []
        match_reasons: set[str] = set()

        for item in evidence_pack.get("order_evidence") or []:
            data = item.get("data") or {}
            order_items = data.get("order_items") or []
            if not order_items:
                order_items = [
                    {"product_id": None, "product_name": name}
                    for name in data.get("items") or []
                ]
            reason = ""
            for order_item in order_items:
                reason = cls._order_product_match_reason(order_item, product)
                if reason:
                    break
            order_info = {
                "order_id": item.get("entity_id"),
                "order_no": data.get("order_no"),
                "items": data.get("items") or [],
            }
            if reason:
                order_entity_id = cls._safe_int(item.get("entity_id"))
                if order_entity_id is not None:
                    selected_order_ids.add(order_entity_id)
                if data.get("order_no"):
                    selected_order_nos.add(str(data["order_no"]))
                selected_orders.append({**order_info, "match_reason": reason})
                match_reasons.add(reason)
            else:
                dropped_orders.append({**order_info, "match_reason": "product_mismatch"})

        def related_order(record: dict) -> bool:
            data = record.get("data") or {}
            order_id = data.get("order_id")
            order_no = str(data.get("order_no") or "")
            try:
                if order_id is not None and int(order_id) in selected_order_ids:
                    return True
            except (TypeError, ValueError):
                pass
            return bool(order_no and order_no in selected_order_nos)

        filtered["order_evidence"] = [
            item
            for item in evidence_pack.get("order_evidence") or []
            if cls._safe_int(item.get("entity_id")) in selected_order_ids
            or str((item.get("data") or {}).get("order_no") or "") in selected_order_nos
        ]
        filtered["shipment_evidence"] = [
            item for item in evidence_pack.get("shipment_evidence") or [] if related_order(item)
        ]
        filtered["return_evidence"] = [
            item for item in evidence_pack.get("return_evidence") or [] if related_order(item)
        ]
        filtered["payment_evidence"] = [
            item
            for item in evidence_pack.get("payment_evidence") or []
            if cls._safe_int((item.get("data") or {}).get("order_id")) in selected_order_ids
        ]
        def related_db_evidence(record: dict) -> bool:
            source_type = record.get("source_type")
            if source_type not in {"order", "shipment", "payment", "return_request"}:
                return True
            fields = record.get("structured_fields") or {}
            if source_type == "order":
                return cls._safe_int(record.get("source_id")) in selected_order_ids or str(
                    fields.get("order_no") or ""
                ) in selected_order_nos
            return related_order({"data": fields})

        filtered["db_evidence"] = [
            item for item in evidence_pack.get("db_evidence") or [] if related_db_evidence(item)
        ]
        filtered["product_order_filter"] = {
            "enabled": True,
            "product_id": product.get("product_id"),
            "product_name": product.get("product_name"),
            "matched_order_count": len(filtered["order_evidence"]),
        }
        filtered["selected_evidence_count"] = len(filtered.get("db_evidence") or []) + len(
            filtered.get("rag_evidence") or []
        )
        if not filtered["order_evidence"]:
            warnings = list(filtered.get("warnings") or [])
            warnings.append("PRODUCT_ORDER_MATCH_NOT_FOUND")
            filtered["warnings"] = warnings

        selected_counts = {
            key: len(filtered.get(key) or [])
            for key in ("order_evidence", "shipment_evidence", "return_evidence", "payment_evidence")
        }
        dropped_counts = {
            key: max(raw_counts[key] - selected_counts[key], 0) for key in raw_counts
        }
        trace = {
            "enabled": True,
            "product_id": product.get("product_id"),
            "product_name": product.get("product_name"),
            "raw_count": raw_counts,
            "selected_count": selected_counts,
            "dropped_count": dropped_counts,
            "selected_orders": selected_orders,
            "dropped_orders": dropped_orders,
            "match_reason": ", ".join(sorted(match_reasons)) if match_reasons else "no_matching_order",
        }
        return filtered, trace

    @staticmethod
    def _route_family(classification: ClassificationResult) -> str:
        domain = (classification.domain or "").strip().upper()
        if domain in {"PRODUCT", "SUPPORT", "MIXED", "OUT_OF_DOMAIN", "UNSAFE", "NONSENSE"}:
            return domain
        if (classification.intent or "").startswith("PRODUCT_"):
            return "PRODUCT"
        return "SUPPORT"

    @staticmethod
    def _looks_like_catalog_question(query: str) -> bool:
        normalized = SupportPipeline._normalize_match_text(query)
        if not normalized:
            return False
        catalog_terms = {
            "fiyat",
            "stok",
            "iade",
            "garanti",
            "yorum",
            "puan",
            "watt",
            "ne kadar",
            "kac para",
            "kaç para",
        }
        return any(term in normalized for term in catalog_terms)

    def _safe_router_fallback(
        self,
        *,
        classification: ClassificationResult,
        original_user_message: str,
        canonical_query: str,
        evidence_pack: dict,
    ) -> str:
        router = evidence_pack.get("router", {})
        requested = router.get("requested_information") or []
        if isinstance(requested, str):
            requested = [requested]
        structured = evidence_pack.get("db_evidence", []) + evidence_pack.get("rag_evidence", [])
        if evidence_pack.get("rag_evidence") and self._has_user_order_evidence(evidence_pack):
            for item in evidence_pack.get("rag_evidence", []):
                summary = self._summarize_evidence_item(item, requested)
                if summary:
                    return summary
        for item in structured:
            summary = self._summarize_evidence_item(item, requested)
            if summary:
                return summary
        for item in structured:
            fields = item.get("structured_fields") or {}
            for key in requested:
                if key and key in fields and fields.get(key) not in {None, "", [], {}}:
                    return str(fields.get(key))
        if structured:
            first = structured[0]
            title = first.get("title_or_name") or ""
            excerpt = first.get("raw_excerpt") or ""
            if title and excerpt:
                return f"{title} ile ilgili mevcut kaynaklarda {excerpt[:220]}."
            if excerpt:
                return str(excerpt)[:300]
        if router.get("intent") in {"OUT_OF_DOMAIN", "UNSAFE", "NONSENSE"}:
            return "Bu istek mevcut destek kapsamı dışında."
        del classification, original_user_message, canonical_query
        return "Bu bilgi mevcut kaynaklarda bulunamadı."

    def _safe_router_fallback_router_first(
        self,
        *,
        classification: ClassificationResult,
        original_user_message: str,
        canonical_query: str,
        evidence_pack: dict,
    ) -> str:
        router = evidence_pack.get("router", {})
        requested = router.get("requested_information") or []
        if isinstance(requested, str):
            requested = [requested]
        structured = evidence_pack.get("db_evidence", []) + evidence_pack.get("rag_evidence", [])
        if evidence_pack.get("rag_evidence") and self._has_user_order_evidence(evidence_pack):
            for item in evidence_pack.get("rag_evidence", []):
                summary = self._summarize_evidence_item(item, requested)
                if summary:
                    return summary
        for item in structured:
            summary = self._summarize_evidence_item(item, requested)
            if summary:
                return summary
        for item in structured:
            fields = item.get("structured_fields") or {}
            for key in requested:
                if key and key in fields and fields.get(key) not in {None, "", [], {}}:
                    return str(fields.get(key))
        if router.get("intent") in {"OUT_OF_DOMAIN", "UNSAFE", "NONSENSE"}:
            return "Bu istek mevcut destek kapsamı dışında."
        del classification, original_user_message, canonical_query
        return "Bu bilgi mevcut kaynaklarda bulunamadı."

    @staticmethod
    def _clean_rag_line(line: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(line or "")).strip(" -\t\r\n")
        cleaned = re.sub(r"^(Tanım|Koşullar|Adımlar|İstisnalar):\s*", "", cleaned)
        return cleaned.strip()

    @classmethod
    def _extract_rag_section_lines(cls, excerpt: str, section_name: str) -> list[str]:
        lines = [str(line).strip() for line in str(excerpt or "").splitlines()]
        section_headers = {
            "Tanım",
            "Kategori",
            "Koşullar",
            "Adımlar",
            "İstisnalar",
            "Destek Gerektiren Durumlar",
        }
        selected: list[str] = []
        in_section = False
        for line in lines:
            stripped = line.strip()
            header = stripped.rstrip(":")
            if header == section_name:
                in_section = True
                continue
            if in_section and header in section_headers:
                break
            if in_section:
                cleaned = cls._clean_rag_line(stripped)
                if cleaned:
                    selected.append(cleaned)
        return selected

    @classmethod
    def _rag_fallback_answer(cls, item: dict) -> str:
        title = str(item.get("title_or_name") or "İlgili destek dokümanı").strip()
        source_id = str(item.get("source_id") or "").strip().upper()
        matched_fields = {
            str(field).strip().casefold()
            for field in (item.get("matched_fields") or [])
            if str(field).strip()
        }
        excerpt = str(item.get("raw_excerpt") or "").strip()
        if not excerpt:
            return f"{title} kaynağında ilgili bilgi bulundu."

        is_return_request_doc = (
            "IADE_TALEBI_OLUSTURMA" in source_id
            or "iade talebi oluşturma" in title.casefold()
        )
        if is_return_request_doc and (
            "adimlar" in matched_fields or "adımlar" in matched_fields
        ):
            steps = cls._extract_rag_section_lines(excerpt, "Adımlar")
            if steps:
                bullets = "\n".join(f"- {step}" for step in steps[:6])
                return f"İade talebi oluşturmak için:\n{bullets}"

        bullets = [
            cls._clean_rag_line(line)
            for line in excerpt.splitlines()
            if line.strip().startswith("-")
        ]
        bullets = [line for line in bullets if line]
        if bullets:
            return f"{title} kaynağına göre:\n" + "\n".join(
                f"- {line}" for line in bullets[:5]
            )

        cleaned_excerpt = cls._clean_rag_line(excerpt)
        cleaned_excerpt = cleaned_excerpt[:500].rstrip()
        return f"{title} kaynağına göre: {cleaned_excerpt}"

    @staticmethod
    def _has_user_order_evidence(evidence_pack: dict) -> bool:
        return bool(
            evidence_pack.get("order_evidence")
            or evidence_pack.get("shipment_evidence")
            or evidence_pack.get("return_evidence")
        )

    @staticmethod
    def _user_order_context_summary(evidence_pack: dict) -> str:
        orders = evidence_pack.get("order_evidence") or []
        shipments_by_order = {
            (item.get("data") or {}).get("order_no"): item.get("data") or {}
            for item in evidence_pack.get("shipment_evidence") or []
            if (item.get("data") or {}).get("order_no")
        }
        returns_by_order = {
            (item.get("data") or {}).get("order_no"): item.get("data") or {}
            for item in evidence_pack.get("return_evidence") or []
            if (item.get("data") or {}).get("order_no")
        }
        lines: list[str] = []
        for item in orders[:5]:
            data = item.get("data") or {}
            order_no = str(data.get("order_no") or "").strip()
            if not order_no:
                continue
            products = ", ".join(str(name) for name in (data.get("items") or [])[:3])
            parts = []
            if products:
                parts.append(products)
            if data.get("order_status"):
                parts.append(f"sipariş {data['order_status']}")
            if data.get("shipping_status"):
                parts.append(f"kargo {data['shipping_status']}")
            shipment = shipments_by_order.get(order_no) or {}
            if shipment.get("tracking_number"):
                parts.append(f"takip {shipment['tracking_number']}")
            return_request = returns_by_order.get(order_no) or {}
            if return_request.get("return_code"):
                parts.append(
                    f"iade {return_request['return_code']} / {return_request.get('return_status')}"
                )
            lines.append(f"- {order_no}: {'; '.join(parts) if parts else 'kayıt bulundu'}")
        if not lines:
            return ""
        return "Sizin siparişlerinizde durum şöyle:\n" + "\n".join(lines)

    def _summarize_evidence_item(
        self, item: dict, requested: list[str] | tuple[str, ...]
    ) -> str:
        fields = item.get("structured_fields") or {}
        source_type = str(item.get("source_type") or "").lower()
        title = str(item.get("title_or_name") or "").strip()
        requested_set = {
            str(key).strip().casefold() for key in requested if str(key).strip()
        }
        if source_type == "product":
            name = str(fields.get("name") or title or "Ürün").strip()
            if "price" in requested_set or fields.get("price") is not None:
                price = fields.get("price")
                currency = fields.get("currency") or "TRY"
                return f"{name} ürününün fiyatı {price} {currency}."
            if "stock" in requested_set or fields.get("stock") is not None:
                stock = fields.get("stock")
                availability = fields.get("availability")
                if availability:
                    return f"{name} için stok durumu {availability}."
                if stock is not None:
                    return f"{name} için stokta {stock} adet görünüyor."
            if "rating_average" in fields or "review_count" in fields:
                rating = fields.get("rating_average")
                count = fields.get("review_count")
                return f"{name} için ortalama puan {rating} / 5 ve {count} yorum var."
            if fields.get("returnable") is not None:
                return (
                    f"{name} iade edilebilir."
                    if fields.get("returnable")
                    else f"{name} iade edilemez."
                )
            if fields.get("description"):
                return f"{name} için mevcut bilgi: {fields.get('description')}."
            return f"{name} için mevcut ürün bilgileri bulundu."

        if source_type == "order":
            order_no = str(fields.get("order_no") or title or "").strip()
            if not order_no:
                return ""
            parts: list[str] = []
            if fields.get("order_status"):
                parts.append(f"sipariş durumu {fields['order_status']}")
            if fields.get("shipping_status"):
                parts.append(f"kargo durumu {fields['shipping_status']}")
            if fields.get("tracking_number"):
                parts.append(f"takip numarası {fields['tracking_number']}")
            if fields.get("estimated_delivery_at"):
                parts.append(f"tahmini teslimat {fields['estimated_delivery_at']}")
            if fields.get("delay_reason"):
                parts.append(f"gecikme nedeni {fields['delay_reason']}")
            if parts:
                return f"{order_no} için {'; '.join(parts)}."
            return f"{order_no} numaralı sipariş için kayıt bulundu."

        if source_type == "shipment":
            order_no = str(fields.get("order_no") or title or "").strip()
            parts: list[str] = []
            if fields.get("shipping_status"):
                parts.append(f"kargo durumu {fields['shipping_status']}")
            if fields.get("tracking_number"):
                parts.append(f"takip numarası {fields['tracking_number']}")
            if fields.get("estimated_delivery_at"):
                parts.append(f"tahmini teslimat {fields['estimated_delivery_at']}")
            if fields.get("delay_reason"):
                parts.append(f"gecikme nedeni {fields['delay_reason']}")
            if parts:
                return f"{order_no or 'Kargo kaydı'} için {'; '.join(parts)}."
            return f"{order_no or 'Kargo kaydı'} bulundu."

        if source_type == "payment":
            reference = str(fields.get("provider_reference") or title or "ödeme kaydı").strip()
            parts: list[str] = []
            if fields.get("status"):
                parts.append(f"durum {fields['status']}")
            if fields.get("amount") is not None:
                parts.append(f"tutar {fields['amount']}")
            if fields.get("order_id") is not None:
                parts.append(f"bağlı sipariş {fields['order_id']}")
            if parts:
                return f"{reference} için {'; '.join(parts)}."
            return f"{reference} için ödeme kaydı bulundu."

        if source_type == "coupon":
            code = str(fields.get("code") or title or "kupon").strip()
            parts: list[str] = []
            if fields.get("status"):
                parts.append(f"durum {fields['status']}")
            if fields.get("discount_value") is not None:
                parts.append(f"indirim {fields['discount_value']}")
            if fields.get("min_cart_total") is not None:
                parts.append(f"minimum sepet {fields['min_cart_total']}")
            if parts:
                return f"{code} için {'; '.join(parts)}."
            return f"{code} için kupon kaydı bulundu."

        if source_type == "cart":
            if fields.get("total") is not None:
                return f"Aktif sepet toplamı {fields['total']}."
            return "Aktif sepet kaydı bulundu."

        if source_type == "return_request":
            return_code = str(fields.get("return_code") or title or "iade kaydı").strip()
            parts: list[str] = []
            if fields.get("return_status"):
                parts.append(f"iade durumu {fields['return_status']}")
            if fields.get("refund_status"):
                parts.append(f"geri ödeme durumu {fields['refund_status']}")
            if parts:
                return f"{return_code} için {'; '.join(parts)}."
            return f"{return_code} için iade kaydı bulundu."

        if source_type == "review":
            if fields.get("rating_average") is not None:
                return f"Ortalama puan {fields['rating_average']} / 5."
            return "İnceleme bilgisi bulundu."
        if source_type == "rag":
            return self._rag_fallback_answer(item)
        return ""

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
        classification: ClassificationResult | None = None,
    ) -> str:
        customer_context = customer_context or {}
        product_context = product_context or {}
        classification = classification or ClassificationResult(
            category="GENEL_DESTEK",
            subcategory="fallback",
            priority="LOW",
            expected_action="RAG_ANSWER",
        )
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
        support_procedure = (
            (classification.domain or "").upper() == "SUPPORT"
            and (classification.requested_info or "").casefold() == "procedure"
        )
        if grouped:
            standard_chunk = await session.scalar(
                select(Chunk.content)
                .where(
                    Chunk.doc_id == grouped[0].doc_id,
                    Chunk.section == "standart_yanit",
                )
                .order_by(Chunk.chunk_id)
            )
            if standard_chunk:
                return str(standard_chunk).strip()
            document = await session.get(Document, grouped[0].doc_id)
            if document:
                standard = str(document.raw_json.get("standart_yanit", "")).strip()
                if standard:
                    return standard
            combined_context = str(grouped[0].combined_context or "").strip()
            if combined_context:
                paragraphs = [
                    part.strip()
                    for part in re.split(r"\n{2,}", combined_context)
                    if part.strip()
                ]
                return (paragraphs[0] if paragraphs else combined_context)[:800].strip()
        if (
            not support_procedure
            and (classification.domain or "").upper() in {"PRODUCT", "MIXED"}
            and product_match_reason in {"ambiguous_catalog_match", "ambiguous_weak_match"}
        ):
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
        trace_id: str | None = None,
    ) -> tuple[
        Message,
        str,
        list[GroupedDocument],
        list[tuple[object, float, int]],
        ClassificationResult,
    ]:
        started = time.perf_counter()
        trace_elapsed: dict[str, float] = {}
        self.current_trace_id = trace_id or ""
        frontend_context = frontend_context or {}
        trace = PipelineTrace(
            trace_id=self.current_trace_id or "no-trace",
            settings=self.settings,
            user_question=safe_query,
            conversation_id=conversation.id,
            user_id=user.id,
        )
        masked_query, pii_findings = mask_pii(safe_query)
        self.last_stage = "previous_customer_context"
        previous_customer_context = await self._last_customer_context(session, conversation)
        followup_reference = self._resolve_followup_reference(
            masked_query, previous_customer_context
        )
        classifier_started = time.perf_counter()
        self.last_stage = "router"
        self._log_stage("router", classifier_started, "start")
        classification = await self.classifier.classify(safe_query, masked_query)
        trace_elapsed["router"] = round((time.perf_counter() - classifier_started) * 1000, 2)
        self._log_stage(
            "router",
            classifier_started,
            "ok",
            f"provider={getattr(self.classifier, 'last_provider', classification.provider)} fallback={getattr(self.classifier, 'last_fallback_used', False)}",
        )
        self._remember_timeout_state(
            classification=classification.as_dict(),
            router=self._router_payload(classification),
        )
        trace.set("router", getattr(self.classifier, "last_router_trace", {}))
        trace.add_stage(
            "router",
            {
                "provider": getattr(self.classifier, "last_provider", classification.provider),
                "fallback_used": getattr(self.classifier, "last_fallback_used", False),
                "fallback_reason": getattr(self.classifier, "last_fallback_reason", ""),
                "raw_output": getattr(self.classifier, "last_router_trace", {}).get("raw_response", ""),
                "parsed_output": self._router_payload(classification),
                "elapsed_ms": trace_elapsed["router"],
            },
        )
        classifier_usage = dict(self.classifier.last_usage)
        self.last_stage = "history_load"
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
            rewrite_started = time.perf_counter()
            self.last_stage = "rewrite"
            try:
                rewrite = await self.rewriter.rewrite(
                    masked_query,
                    history,
                    use_dev_model=True,
                )
                rewrite_usage = dict(self.gemini.last_usage)
                self._log_stage(
                    "rewrite",
                    rewrite_started,
                    "ok",
                    f"in_scope={rewrite.get('is_in_scope', True)}",
                )
            except asyncio.TimeoutError as exc:
                pipeline_errors.append("REWRITE_TIMEOUT")
                rewrite = {
                    "canonical_query": masked_query,
                    "category": classification.category,
                    "is_in_scope": True,
                }
                self._log_stage("rewrite", rewrite_started, "timeout", type(exc).__name__)
            except GeminiServiceError:
                pipeline_errors.append("GEMINI_REWRITE_UNAVAILABLE")
                rewrite = {
                    "canonical_query": masked_query,
                    "category": classification.category,
                    "is_in_scope": True,
                }
                self._log_stage("rewrite", rewrite_started, "error", "GeminiServiceError")
        canonical = rewrite.get("canonical_query", masked_query).strip() or masked_query
        category = classification.category
        if followup_reference:
            canonical = (
                f"{followup_reference['order_no']} numaralı sipariş bağlamında: "
                f"{canonical}"
                if followup_reference.get("order_no")
                else f"{followup_reference['category']} bağlamında: {canonical}"
            )
        resolver_scope = bool(rewrite.get("is_in_scope", True)) and (
            classification.expected_action != "REJECT"
        )
        self.last_stage = "conversation_state"
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
        trace.set("context_plan", context_plan_metadata)
        trace.add_stage(
            "context_resolver",
            {
                "next_step": context_plan.next_step,
                "data_sources": context_plan.data_sources,
                "fields": context_plan.fields,
                "needs_support_rag": context_plan.needs_support_rag,
                "required_contexts": self._evidence_required_contexts(context_plan),
                "resolved_entities": context_plan.resolved_entities.model_dump(mode="json"),
                "warnings": context_plan.warnings,
            },
        )
        route_family = self._route_family(classification)
        if frontend_context.get("current_product_id"):
            route_family = "PRODUCT"
        product_followup_rescue_allowed = bool(
            getattr(conversation_state, "last_product_id", None)
        ) and self._looks_like_catalog_question(f"{canonical} {safe_query}")
        generic_policy_question = self._is_generic_policy_question(
            classification,
            context_plan,
            safe_query,
            frontend_context,
        )
        planning_result = self._planning_result(
            classification,
            context_plan,
            query=safe_query,
            frontend_context=frontend_context,
            route_family=route_family,
            generic_policy_question=generic_policy_question,
            followup_catalog_question=product_followup_rescue_allowed,
        )
        required_contexts = self._planned_required_contexts(
            self._evidence_required_contexts(context_plan),
            planning_result,
            context_plan,
        )
        suppressed_data_sources = []
        if generic_policy_question:
            suppressed_data_sources.extend(
                source
                for source in ("order_db", "product_db", "return_db", "payment_db", "review_db")
                if source in set(context_plan.data_sources)
            )
            if not suppressed_data_sources:
                suppressed_data_sources.append("user_context_for_generic_policy")
        trace.set("planning_result", planning_result)
        trace.add_stage(
            "planning",
            {
                "planning_result": planning_result,
                "required_contexts": required_contexts,
                "suppressed_data_sources": suppressed_data_sources,
            },
        )
        needs_user_order_context = self._needs_user_order_context(
            classification, context_plan
        ) and not generic_policy_question
        deterministic_db_lookup_needed = bool(
            planning_result["should_use_order_db"]
            or planning_result["should_use_return_db"]
            or planning_result["should_use_payment_db"]
            or "coupon_db" in set(context_plan.data_sources)
            or "cart_db" in set(context_plan.data_sources)
            or context_plan.resolved_entities.product_id is not None
            or frontend_context.get("current_order_id")
            or frontend_context.get("current_payment_id")
            or frontend_context.get("current_return_id")
        )
        resolver_fetches_context = (
            context_plan.next_step == "FETCH_CONTEXT"
            and not context_plan.needs_clarification
            and deterministic_db_lookup_needed
        ) or needs_user_order_context
        data_resolution = self._skipped_data_resolution()
        data_started = None
        if resolver_fetches_context:
            data_resolver = self.data_resolver or DataResolver(
                SqlAlchemyDataResolverAdapter(session)
            )
            data_started = time.perf_counter()
            self.last_stage = "data_resolver"
            self._log_stage("data_resolver", data_started, "start")
            try:
                data_resolution = await asyncio.wait_for(
                    data_resolver.resolve(
                        self._data_resolver_input(
                            user_id=user.id,
                            message=masked_query,
                            context_plan=context_plan,
                            conversation_state=conversation_state,
                            frontend_context=frontend_context,
                        )
                    ),
                    timeout=self._stage_timeout("data_resolver", self.settings.llm_timeout_seconds),
                )
                self._log_stage(
                    "data_resolver",
                    data_started,
                    "ok",
                    f"status={data_resolution.status.value}",
                )
            except asyncio.TimeoutError as exc:
                pipeline_errors.append("DATA_RESOLVER_TIMEOUT")
                data_resolution = self._skipped_data_resolution()
                self._log_stage("data_resolver", data_started, "timeout", type(exc).__name__)
        if needs_user_order_context and data_resolution.status == DataResolutionStatus.SKIP:
            data_resolution = self._user_order_context_resolution()
        trace_elapsed["db_lookup"] = (
            round((time.perf_counter() - data_started) * 1000, 2)
            if data_started is not None
            else 0.0
        )
        data_resolution_metadata = data_resolution.model_dump(mode="json")
        trace.set("db_lookup", data_resolution_metadata)
        trace.add_stage(
            "data_resolver",
            {
                "resolver_fetches_context": resolver_fetches_context,
                "status": data_resolution.status.value,
                "resolved_entities": data_resolution.resolved_entities.model_dump(mode="json"),
                "entity_results": [
                    item.model_dump(mode="json") for item in data_resolution.entity_results
                ],
                "evidence_refs": [
                    item.model_dump(mode="json") for item in data_resolution.evidence_refs
                ],
                "warnings": data_resolution.warnings,
                "elapsed_ms": trace_elapsed["db_lookup"],
            },
        )
        data_allows_context = self._data_resolution_allows_context(data_resolution)
        pipeline_fetches_context = resolver_fetches_context and data_allows_context
        data_resolution_blocks_context = (
            resolver_fetches_context and not data_allows_context
        )
        evidence_output = EvidenceFetcherOutput()
        evidence_started = None
        if pipeline_fetches_context and self.evidence_fetcher is not None:
            evidence_started = time.perf_counter()
            self.last_stage = "evidence_fetcher"
            try:
                evidence_fetcher = self.evidence_fetcher
                adapter = getattr(evidence_fetcher, "adapter", None)
                if isinstance(adapter, SqlAlchemyEvidenceFetcherAdapter):
                    evidence_fetcher = EvidenceFetcher(
                        adapter.bind(session)
                    )
                evidence_output = await asyncio.wait_for(
                    evidence_fetcher.fetch(
                        {
                            "user_id": user.id,
                            "context_plan": context_plan.model_dump(mode="json"),
                            "data_resolution": data_resolution.model_dump(mode="json"),
                            "required_contexts": required_contexts,
                        }
                    ),
                    timeout=self._stage_timeout("evidence_fetcher", self.settings.llm_timeout_seconds),
                )
                if needs_user_order_context:
                    adapter = getattr(evidence_fetcher, "adapter", None)
                    if adapter is not None:
                        recent_context = await asyncio.wait_for(
                            adapter.fetch_recent_user_order_context(user.id),
                            timeout=self._stage_timeout(
                                "evidence_fetcher",
                                self.settings.llm_timeout_seconds,
                            ),
                        )
                        evidence_output = self._merge_evidence_output(
                            evidence_output, recent_context
                        )
                self._log_stage(
                    "evidence_fetcher",
                    evidence_started,
                    "ok",
                    f"selected={len(evidence_output.product_evidence) + len(evidence_output.order_evidence) + len(evidence_output.shipment_evidence) + len(evidence_output.payment_evidence) + len(evidence_output.coupon_evidence) + len(evidence_output.cart_evidence) + len(evidence_output.return_evidence) + len(evidence_output.review_evidence)}",
                )
            except asyncio.TimeoutError as exc:
                pipeline_errors.append("EVIDENCE_FETCHER_TIMEOUT")
                evidence_output = EvidenceFetcherOutput()
                self._log_stage("evidence_fetcher", evidence_started, "timeout", type(exc).__name__)
            except Exception as exc:
                safe_error_summary = type(exc).__name__
                evidence_output.warnings.append(
                    f"EVIDENCE_FETCHER_ERROR:{safe_error_summary}"
                )
                pipeline_errors.append("EVIDENCE_FETCHER_ERROR")
                self._log_stage("evidence_fetcher", evidence_started, "error", safe_error_summary)
        trace_elapsed["evidence"] = (
            round((time.perf_counter() - evidence_started) * 1000, 2)
            if evidence_started is not None
            else 0.0
        )
        evidence_metadata = evidence_output.model_dump(mode="json")
        trace.set("selected_records", evidence_metadata)
        trace.add_stage(
            "evidence_fetcher",
            {
                "pipeline_fetches_context": pipeline_fetches_context,
                "output": evidence_metadata,
                "elapsed_ms": trace_elapsed["evidence"],
            },
        )
        effective_frontend_context = dict(frontend_context)
        resolved_data_entities = data_resolution.resolved_entities
        order_canonical_product_id = self._canonical_product_from_order_evidence(
            evidence_output
        )
        if resolved_data_entities.product_id is not None:
            effective_frontend_context["current_product_id"] = (
                resolved_data_entities.product_id
            )
        elif (
            order_canonical_product_id is not None
            and not effective_frontend_context.get("current_product_id")
        ):
            effective_frontend_context["current_product_id"] = order_canonical_product_id
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
            security_metadata=self._json_safe({
                "pii_masked": pii_findings,
                "classification": classification.as_dict(),
                "context_resolver": context_plan_metadata,
                "data_resolver": data_resolution_metadata,
                "evidence_fetcher": evidence_metadata,
            }),
        )
        session.add(user_message)
        await session.flush()

        product_context_started = time.perf_counter()
        has_canonical_product_context = bool(
            effective_frontend_context.get("current_product_id")
        )
        product_context_allowed = (
            (
                legacy_context_allowed
                and planning_result["should_use_product_db"]
                and (
                    has_canonical_product_context
                    or planning_result["should_use_product_fuzzy"]
                )
            )
            or (route_family == "PRODUCT" and planning_result["should_use_product_db"])
            or has_canonical_product_context
            or product_followup_rescue_allowed
        )
        if product_context_allowed:
            try:
                self.last_stage = "product_context"
                product_context = await asyncio.wait_for(
                    self.product_context.build(
                        session,
                        user,
                        category,
                        canonical,
                        conversation=conversation,
                        selected_order_no=selected_order_no,
                        frontend_context=effective_frontend_context,
                        original_query=safe_query,
                        allow_alias_probe=route_family == "OUT_OF_DOMAIN",
                    ),
                    timeout=self._stage_timeout("product_context", self.settings.llm_timeout_seconds),
                )
                self._log_stage(
                    "product_context",
                    product_context_started,
                    "ok",
                    f"items={len(product_context.get('items', []))} route_mode={product_context.get('route_mode')}",
                )
            except asyncio.TimeoutError as exc:
                product_context = {
                    "route_mode": "resolver_no_fetch",
                    "category": category,
                    "context_type": "clarification_needed",
                    "items": [],
                    "text": "",
                    "decision_hints": [],
                }
                self._log_stage("product_context", product_context_started, "timeout", type(exc).__name__)
        else:
            product_context = {
                "route_mode": route_family.lower() if route_family else (
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
        route_mode = product_context.get("route_mode", route_family.lower() or "support_only")
        customer_context_started = time.perf_counter()
        if legacy_context_allowed and route_family in {"SUPPORT", "MIXED"}:
            try:
                self.last_stage = "customer_context"
                support_context = await asyncio.wait_for(
                    self.customer_context.build(
                        session,
                        user,
                        category,
                        canonical,
                        selected_order_no=selected_order_no,
                        selected_order_id=resolved_data_entities.order_id,
                    ),
                    timeout=self._stage_timeout("customer_context", self.settings.llm_timeout_seconds),
                )
                self._log_stage(
                    "customer_context",
                    customer_context_started,
                    "ok",
                    f"items={len(support_context.get('items', []))}",
                )
            except asyncio.TimeoutError as exc:
                support_context = {"category": category, "items": [], "text": ""}
                self._log_stage("customer_context", customer_context_started, "timeout", type(exc).__name__)
        else:
            support_context = {"category": category, "items": [], "text": ""}
        support_in_scope = route_family in {"SUPPORT", "MIXED"} and (
            pipeline_fetches_context or planning_result["should_use_rag"]
        )
        product_context_has_product = bool(
            product_context.get("text") or product_context.get("selected_product_ids")
        )
        product_in_scope = (
            (pipeline_fetches_context or product_context_allowed)
            and (
                route_family in {"PRODUCT", "MIXED", "OUT_OF_DOMAIN"}
                or product_followup_rescue_allowed
            )
            and product_context_has_product
        )
        in_scope = support_in_scope or product_in_scope
        self.last_stage = "product_context"
        evidence_output = self._merge_product_context_evidence(
            evidence_output,
            product_context,
        )
        trace.set(
            "product_resolution",
            {
                "product_id_source": product_context.get("product_id_source", ""),
                "alias_type_match_source": product_context.get("alias_type_match_source", ""),
                "candidate_products": product_context.get("top_candidates", []),
                "candidate_groups": product_context.get("candidate_groups", []),
                "selected_product": product_context.get("selected_product", {}),
                "selected_group": product_context.get("selected_group", {}),
                "confidence": product_context.get("product_match_score", 0),
                "reason": product_context.get("product_match_reason", ""),
                "answer_mode": product_context.get("answer_mode", ""),
                "canonical_product_id": product_context.get("canonical_product_id"),
                "canonical_product_source": product_context.get("canonical_product_source", ""),
                "product_group_suppressed_reason": product_context.get("product_group_suppressed_reason", ""),
                "fuzzy_suppressed_reason": product_context.get("fuzzy_suppressed_reason", ""),
                "conflicting_product_ids": product_context.get("conflicting_product_ids", []),
                "explicit_product_candidates": product_context.get("explicit_product_candidates", []),
                "rejected_candidates": product_context.get("rejected_candidates", []),
                "is_followup": product_context.get("is_followup", False),
                "is_correction": product_context.get("is_correction", False),
                "clarification_needed": product_context.get("clarification_needed", False),
                "state_updated": product_context.get("state_updated", False),
            },
        )
        grouped = []
        structured_evidence_pack = self._structured_evidence_pack(
            classification=classification,
            context_plan=context_plan,
            data_resolution=data_resolution,
            evidence_output=evidence_output,
            grouped=grouped,
            route_family=route_family,
        )
        structured_evidence_pack["product_resolution"] = {
            "product_id_source": product_context.get("product_id_source", ""),
            "alias_type_match_source": product_context.get("alias_type_match_source", ""),
            "candidate_products": product_context.get("top_candidates", []),
            "candidate_groups": product_context.get("candidate_groups", []),
            "selected_product": product_context.get("selected_product", {}),
            "selected_group": product_context.get("selected_group", {}),
            "confidence": product_context.get("product_match_score", 0),
            "reason": product_context.get("product_match_reason", ""),
            "answer_mode": product_context.get("answer_mode", ""),
            "canonical_product_id": product_context.get("canonical_product_id"),
            "canonical_product_source": product_context.get("canonical_product_source", ""),
            "product_group_suppressed_reason": product_context.get("product_group_suppressed_reason", ""),
            "fuzzy_suppressed_reason": product_context.get("fuzzy_suppressed_reason", ""),
            "conflicting_product_ids": product_context.get("conflicting_product_ids", []),
            "explicit_product_candidates": product_context.get("explicit_product_candidates", []),
            "rejected_candidates": product_context.get("rejected_candidates", []),
            "is_followup": product_context.get("is_followup", False),
            "is_correction": product_context.get("is_correction", False),
            "clarification_needed": product_context.get("clarification_needed", False),
            "state_updated": product_context.get("state_updated", False),
        }
        structured_evidence_pack["frontend_context"] = {
            key: effective_frontend_context[key]
            for key in ("current_product_id", "current_order_id", "current_cart_id", "current_return_id", "current_payment_id", "page_context")
            if effective_frontend_context.get(key) is not None
        }
        self._remember_timeout_state(
            canonical_query=canonical,
            route_family=route_family,
            structured_evidence_pack=structured_evidence_pack,
        )
        evidence_metadata = structured_evidence_pack
        user_message.security_metadata = {
            **(user_message.security_metadata or {}),
            "router": self._router_payload(classification),
            "evidence_pack": structured_evidence_pack,
        }
        user_message.security_metadata = self._json_safe(user_message.security_metadata)
        debug_metadata = {
            "route_mode": route_mode,
            "route_family": route_family,
            "router": self._router_payload(classification),
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
                "product_id_source": product_context.get("product_id_source", ""),
                "alias_type_match_source": product_context.get("alias_type_match_source", ""),
                "candidate_products": product_context.get("top_candidates", []),
                "candidate_groups": product_context.get("candidate_groups", []),
                "selected_product": product_context.get("selected_product", {}),
                "selected_group": product_context.get("selected_group", {}),
                "answer_mode": product_context.get("answer_mode", ""),
                "canonical_product_id": product_context.get("canonical_product_id"),
                "canonical_product_source": product_context.get("canonical_product_source", ""),
                "product_group_suppressed_reason": product_context.get("product_group_suppressed_reason", ""),
                "fuzzy_suppressed_reason": product_context.get("fuzzy_suppressed_reason", ""),
                "conflicting_product_ids": product_context.get("conflicting_product_ids", []),
                "explicit_product_candidates": product_context.get("explicit_product_candidates", []),
                "rejected_candidates": product_context.get("rejected_candidates", []),
                "is_followup": product_context.get("is_followup", False),
                "is_correction": product_context.get("is_correction", False),
                "clarification_needed": product_context.get("clarification_needed", False),
                "state_updated": product_context.get("state_updated", False),
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
            "db_called": False,
            "rag_called": False,
            "support_rag_used": False,
            "product_context_used": False,
            "customer_context_used": False,
        }
        grouped = []
        should_run_support_rag = (
            planning_result["should_use_rag"]
            and (support_in_scope or product_in_scope)
            and route_family in {"SUPPORT", "MIXED", "PRODUCT"}
        )
        retrieval_query = f"{canonical} {safe_query}".strip()
        rag_total_started = time.perf_counter()
        if should_run_support_rag:
            rag_started = time.perf_counter()
            self.last_stage = "retrieval"
            self._log_stage("retrieval", rag_started, "start")
            try:
                grouped = await asyncio.wait_for(
                    self.retrieval.grouped_search(
                        session,
                        retrieval_query,
                        candidate_limit=24,
                        max_documents=2,
                        max_sections=3,
                    ),
                    timeout=self._stage_timeout("retrieval", self.settings.llm_timeout_seconds),
                )
                self._log_stage(
                    "retrieval",
                    rag_started,
                    "ok",
                    f"grouped={len(grouped)} query_len={len(retrieval_query)}",
                )
            except asyncio.TimeoutError as exc:
                grouped = []
                pipeline_errors.append("RETRIEVAL_TIMEOUT")
                self._log_stage("retrieval", rag_started, "timeout", type(exc).__name__)
            except HTTPException:
                pipeline_errors.append("RETRIEVAL_UNAVAILABLE")
        if should_run_support_rag and not grouped and support_context.get("text"):
            fallback_rag_started = time.perf_counter()
            self.last_stage = "retrieval_category"
            self._log_stage("retrieval_category", fallback_rag_started, "start")
            try:
                grouped = await asyncio.wait_for(
                    self.retrieval.grouped_by_category(
                        session,
                        category,
                        max_documents=2,
                        max_sections=3,
                    ),
                    timeout=self._stage_timeout("retrieval", self.settings.llm_timeout_seconds),
                )
                self._log_stage(
                    "retrieval_category",
                    fallback_rag_started,
                    "ok",
                    f"grouped={len(grouped)} category={category}",
                )
            except asyncio.TimeoutError as exc:
                grouped = []
                pipeline_errors.append("CATEGORY_RETRIEVAL_TIMEOUT")
                self._log_stage("retrieval_category", fallback_rag_started, "timeout", type(exc).__name__)
            except HTTPException:
                pipeline_errors.append("CATEGORY_RETRIEVAL_UNAVAILABLE")
        rerank_started = time.perf_counter()
        self.last_stage = "reranker"
        grouped, reranker_score = await self.reranker.rerank(canonical, grouped)
        self._log_stage("reranker", rerank_started, "ok", f"grouped={len(grouped)}")
        trace_elapsed["rag"] = round((time.perf_counter() - rag_total_started) * 1000, 2)
        structured_evidence_pack = self._structured_evidence_pack(
            classification=classification,
            context_plan=context_plan,
            data_resolution=data_resolution,
            evidence_output=evidence_output,
            grouped=grouped,
            route_family=route_family,
        )
        structured_evidence_pack["product_resolution"] = {
            "product_id_source": product_context.get("product_id_source", ""),
            "alias_type_match_source": product_context.get("alias_type_match_source", ""),
            "candidate_products": product_context.get("top_candidates", []),
            "candidate_groups": product_context.get("candidate_groups", []),
            "selected_product": product_context.get("selected_product", {}),
            "selected_group": product_context.get("selected_group", {}),
            "confidence": product_context.get("product_match_score", 0),
            "reason": product_context.get("product_match_reason", ""),
            "answer_mode": product_context.get("answer_mode", ""),
            "canonical_product_id": product_context.get("canonical_product_id"),
            "canonical_product_source": product_context.get("canonical_product_source", ""),
            "product_group_suppressed_reason": product_context.get("product_group_suppressed_reason", ""),
            "fuzzy_suppressed_reason": product_context.get("fuzzy_suppressed_reason", ""),
            "conflicting_product_ids": product_context.get("conflicting_product_ids", []),
            "explicit_product_candidates": product_context.get("explicit_product_candidates", []),
            "rejected_candidates": product_context.get("rejected_candidates", []),
            "is_followup": product_context.get("is_followup", False),
            "is_correction": product_context.get("is_correction", False),
            "clarification_needed": product_context.get("clarification_needed", False),
            "state_updated": product_context.get("state_updated", False),
        }
        structured_evidence_pack["frontend_context"] = {
            key: effective_frontend_context[key]
            for key in ("current_product_id", "current_order_id", "current_cart_id", "current_return_id", "current_payment_id", "page_context")
            if effective_frontend_context.get(key) is not None
        }
        evidence_metadata = structured_evidence_pack
        user_message.security_metadata = {
            **(user_message.security_metadata or {}),
            "router": self._router_payload(classification),
            "evidence_pack": structured_evidence_pack,
        }
        user_message.security_metadata = self._json_safe(user_message.security_metadata)
        debug_metadata["retrieved_doc_ids"] = [
            {"doc_id": item.doc_id, "score": item.best_score} for item in grouped
        ]
        raw_rag_chunks = [
            {
                "chunk_id": item.chunk_id,
                "doc_id": item.doc_id,
                "title": item.title,
                "category": item.category,
                "subcategory": item.subcategory,
                "section": item.section,
                "score": item.score,
                "content_preview": item.content[:500],
            }
            for item in getattr(self.retrieval, "last_retrieved_chunks", [])
        ]
        grouped_rag_docs = [
            {
                "doc_id": item.doc_id,
                "title": item.title,
                "category": item.category,
                "subcategory": item.subcategory,
                "best_score": item.best_score,
                "matched_sections": item.matched_sections,
                "combined_context_preview": item.combined_context[:800],
            }
            for item in grouped
        ]
        trace.set(
            "rag",
            {
                "called": bool(grouped),
                "query": retrieval_query,
                "chunks": raw_rag_chunks,
                "grouped_docs": grouped_rag_docs,
                "elapsed_ms": trace_elapsed["rag"],
            },
        )
        trace.add_stage(
            "rag_retrieval",
            {
                "called": bool(grouped),
                "query": retrieval_query,
                "chunks": raw_rag_chunks,
                "grouped_docs": grouped_rag_docs,
                "elapsed_ms": trace_elapsed["rag"],
            },
        )
        answer_evidence_pack, product_order_filter_trace = (
            self._filter_product_related_user_evidence(
                structured_evidence_pack, classification
            )
        )
        data_sources_used = [
            key
            for key in (
                "product_evidence",
                "order_evidence",
                "shipment_evidence",
                "payment_evidence",
                "coupon_evidence",
                "cart_evidence",
                "return_evidence",
                "review_evidence",
                "rag_evidence",
            )
            if answer_evidence_pack.get(key)
        ]
        selected_order_id = None
        if answer_evidence_pack.get("order_evidence"):
            selected_order_id = answer_evidence_pack["order_evidence"][0].get("entity_id")
        selected_product_ids = [
            item.get("entity_id")
            for item in answer_evidence_pack.get("product_evidence", [])
            if item.get("entity_id") is not None
        ]
        product_resolution_trace = answer_evidence_pack.get("product_resolution", {}) or {}
        fuzzy_used = product_resolution_trace.get("product_id_source") == "explicit_fuzzy"
        answer_evidence_pack["user_question"] = safe_query
        answer_evidence_pack["intent"] = classification.intent
        answer_evidence_pack["selected_entities"] = {
            "order_id": selected_order_id,
            "product_ids": selected_product_ids,
            "resolved_entities": resolved_data_entities.model_dump(mode="json"),
        }
        answer_evidence_pack["fetched_data"] = {
            key: answer_evidence_pack.get(key, [])
            for key in (
                "product_evidence",
                "order_evidence",
                "shipment_evidence",
                "payment_evidence",
                "coupon_evidence",
                "cart_evidence",
                "return_evidence",
                "review_evidence",
            )
        }
        answer_evidence_pack["rag_docs"] = answer_evidence_pack.get("rag_evidence", [])
        answer_evidence_pack["missing_data"] = answer_evidence_pack.get("missing_evidence", [])
        answer_evidence_pack["planning_result"] = planning_result
        trace.set("evidence_pack", answer_evidence_pack)
        trace.set("selected_order_id", selected_order_id)
        trace.set("selected_product_ids", selected_product_ids)
        trace.set("data_sources_used", data_sources_used)
        trace.set("suppressed_data_sources", suppressed_data_sources)
        trace.set("fuzzy_used", fuzzy_used)
        trace.set(
            "fuzzy_suppressed_reason",
            product_resolution_trace.get("fuzzy_suppressed_reason", ""),
        )
        trace.set("product_order_filter", product_order_filter_trace)
        trace.add_stage("product_order_filter", product_order_filter_trace)
        debug_metadata["db_called"] = bool(
            resolver_fetches_context
            or bool(product_context.get("text"))
            or bool(support_context.get("text"))
        )
        debug_metadata["rag_called"] = bool(grouped)
        debug_metadata["support_rag_used"] = bool(grouped)
        debug_metadata["product_context_used"] = bool(product_context.get("text"))
        debug_metadata["customer_context_used"] = bool(support_context.get("text"))

        similar = (
            []
        )
        if support_in_scope:
            similar_started = time.perf_counter()
            try:
                self.last_stage = "similar"
                similar = await asyncio.wait_for(
                    self.similar.search(session, retrieval_query, category, limit=3),
                    timeout=self._stage_timeout("similar", self.settings.llm_timeout_seconds),
                )
                self._log_stage("similar", similar_started, "ok", f"candidates={len(similar)}")
            except asyncio.TimeoutError as exc:
                similar = []
                pipeline_errors.append("SIMILAR_TIMEOUT")
                self._log_stage("similar", similar_started, "timeout", type(exc).__name__)
        few_shots = [
            {
                "question": solution.canonical_question,
                "answer": solution.safe_answer,
                "success_rate": solution.success_rate,
            }
            for solution, _, views in similar[:2]
            if views >= self.settings.similar_solution_min_views
        ]
        deterministic_started = time.perf_counter()
        compact_context = build_compact_context(answer_evidence_pack, classification)
        deterministic_result = build_deterministic_answer(
            question=safe_query,
            classification=classification,
            evidence_pack=answer_evidence_pack,
            compact_context=compact_context,
        )
        deterministic_answer_draft = deterministic_result.get("answer", "")
        llm_context = compact_policy_text(compact_context)
        trace_elapsed["deterministic"] = round(
            (time.perf_counter() - deterministic_started) * 1000, 2
        )
        product_group_answer = bool(
            answer_evidence_pack.get("product_resolution", {}).get("selected_group")
        )
        final_answer_mode = deterministic_result.get("answer_mode", "") or (
            "PRODUCT_GROUP" if product_group_answer else ""
        )
        debug_metadata["final_answer_mode"] = final_answer_mode
        trace.set("compact_context", compact_context)
        trace.set(
            "deterministic_fallback_draft",
            {
                "answer": deterministic_answer_draft,
                "source": deterministic_result.get("source", ""),
                "answer_mode": final_answer_mode,
            },
        )
        trace.set("final_answer_mode", final_answer_mode)
        trace.add_stage(
            "deterministic_fallback",
            {
                "compact_context": compact_context,
                "fallback_draft": deterministic_answer_draft,
                "source": deterministic_result.get("source", ""),
                "answer_mode": final_answer_mode,
                "elapsed_ms": trace_elapsed["deterministic"],
            },
        )
        available_sources = [
            {"doc_id": item.doc_id, "title": item.title} for item in grouped
        ]
        generated = {"answer": "", "cited_doc_ids": []}
        answer_usage: dict = {}
        evidence_sections = (
            "product_evidence",
            "order_evidence",
            "shipment_evidence",
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
        if self.settings.gemini_polish_enabled and in_scope and (
            grouped
            or support_context.get("text")
            or product_context.get("text")
            or has_evidence_context
        ):
            try:
                gemini_started = time.perf_counter()
                self.last_stage = "gemini_answer"
                self._log_stage("gemini_answer", gemini_started, "start")
                debug_metadata["gemini_called"] = self.gemini.enabled
                generated = await self.gemini.answer(
                    canonical,
                    history,
                    support_context.get("text", ""),
                    product_context.get("text", ""),
                    llm_context,
                    few_shots,
                    available_sources,
                    original_user_message=safe_query,
                    resolved_entities=resolved_data_entities.model_dump(mode="json"),
                    evidence_pack=answer_evidence_pack,
                    router_json=self._router_payload(classification),
                    answer_scope=answer_scope,
                    compact_context=compact_context,
                    deterministic_draft=None,
                    use_dev_model=True,
                )
                answer_usage = dict(self.gemini.last_usage)
                trace_elapsed["gemini"] = round((time.perf_counter() - gemini_started) * 1000, 2)
                trace.set("gemini", self.gemini.last_trace)
                trace.set(
                    "gemini_prompt_preview",
                    self.gemini.last_trace.get("prompt_preview", ""),
                )
                trace.add_stage(
                    "gemini_answer",
                    {
                        "called": debug_metadata["gemini_called"],
                        "trace": self.gemini.last_trace,
                        "elapsed_ms": trace_elapsed["gemini"],
                    },
                )
                self._log_stage("gemini_answer", gemini_started, "ok", f"cited={len(generated.get('cited_doc_ids', []))}")
            except asyncio.TimeoutError as exc:
                trace_elapsed["gemini"] = round((time.perf_counter() - gemini_started) * 1000, 2)
                pipeline_errors.append("GEMINI_ANSWER_TIMEOUT")
                debug_metadata["gemini_error"] = "TimeoutError"
                trace.set(
                    "gemini_prompt_preview",
                    self.gemini.last_trace.get("prompt_preview", ""),
                )
                trace.add_stage(
                    "gemini_answer",
                    {
                        "called": debug_metadata["gemini_called"],
                        "error": "TimeoutError",
                        "elapsed_ms": trace_elapsed["gemini"],
                    },
                )
                self._log_stage("gemini_answer", gemini_started, "timeout", type(exc).__name__)
            except GeminiServiceError as exc:
                trace_elapsed["gemini"] = round((time.perf_counter() - gemini_started) * 1000, 2)
                pipeline_errors.append("GEMINI_ANSWER_UNAVAILABLE")
                debug_metadata["gemini_error"] = "GeminiServiceError"
                trace.set(
                    "gemini_prompt_preview",
                    self.gemini.last_trace.get("prompt_preview", ""),
                )
                trace.add_stage(
                    "gemini_answer",
                    {
                        "called": debug_metadata["gemini_called"],
                        "error": "GeminiServiceError",
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                        "trace": self.gemini.last_trace,
                        "elapsed_ms": trace_elapsed["gemini"],
                    },
                )
                self._log_stage("gemini_answer", gemini_started, "error", str(exc))
        elif not self.settings.gemini_polish_enabled:
            trace_elapsed["gemini"] = 0.0
            debug_metadata["gemini_called"] = False
            debug_metadata["fallback_reason"] = "gemini_polish_disabled"
            trace.add_stage(
                "gemini_answer",
                {
                    "called": False,
                    "skipped": True,
                    "reason": "GEMINI_POLISH_DISABLED",
                    "elapsed_ms": 0.0,
                },
            )
        elif not in_scope:
            debug_metadata["fallback_reason"] = "out_of_scope"
        else:
            debug_metadata["fallback_reason"] = "no_context"
        self._remember_timeout_state(
            canonical_query=canonical,
            route_family=route_family,
            structured_evidence_pack=structured_evidence_pack,
            classification=classification.as_dict(),
        )
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
        elif (
            context_plan.next_step == "CLARIFY" or context_plan.needs_clarification
        ) and not needs_user_order_context and not product_context_has_product:
            answer = self._resolver_clarification_message(
                context_plan.clarification_reason
            )
            debug_metadata["fallback_reason"] = (
                context_plan.clarification_reason or "context_resolver_clarification"
            )
            debug_metadata["formatter_mode"] = "resolver_clarification"
        elif (
            context_plan.next_step == "FALLBACK"
            and not product_context.get("text")
            and not product_group_answer
            and not grouped
        ):
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
        elif not in_scope and not product_group_answer and not product_context_has_product:
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
            answer = deterministic_answer_draft
            debug_metadata["formatter_mode"] = "deterministic_draft"
        else:
            debug_metadata["formatter_mode"] = "gemini_natural"
        if False and (
            needs_user_order_context
            and answer
            and self._has_user_order_evidence(structured_evidence_pack)
            and debug_metadata["formatter_mode"]
            not in {
                "resolver_clarification",
                "data_resolver_clarification",
                "out_of_scope_plain",
                "clarification_natural",
            }
        ):
            user_order_summary = self._user_order_context_summary(
                structured_evidence_pack
            )
            if (
                user_order_summary
                and "Sizin siparişlerinizde durum şöyle" not in answer
            ):
                answer = f"{answer.rstrip()}\n\n{user_order_summary}"
        payment_items = [str(item) for item in product_context.get("payment_items", [])]
        no_order_payment_item = next(
            (
                item
                for item in payment_items
                if "CAPTURED_NO_ORDER" in item and "siparişe bağlı değil" in item
            ),
            "",
        )
        if False and no_order_payment_item:
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
        gemini_polish_used = debug_metadata["formatter_mode"] == "gemini_natural"
        trace.set("gemini_polish_used", gemini_polish_used)
        answer_source = (
            "gemini"
            if debug_metadata["formatter_mode"] == "gemini_natural"
            else "deterministic_fallback"
            if debug_metadata["formatter_mode"] == "deterministic_draft"
            else "safe_fallback"
            if debug_metadata["formatter_mode"] in {
                "fallback_natural",
                "resolver_clarification",
                "data_resolver_clarification",
                "out_of_scope_plain",
                "clarification_natural",
                "payment_no_order_context",
            }
            else "router_refusal"
            if debug_metadata["formatter_mode"] == "out_of_scope_plain"
            else "safe_fallback"
        )
        debug_metadata["answer_source"] = answer_source
        trace.set("final_answer_source", answer_source)
        logger.info(
            "router_evidence_trace trace_id=%s domain=%s intent=%s category=%s subcategory=%s entities=%s requested_information=%s db_called=%s rag_called=%s selected_evidence_count=%s gemini_called=%s answer_source=%s final_metadata=%s",
            self.current_trace_id,
            classification.domain,
            classification.intent,
            classification.category,
            classification.subcategory,
            classification.entities,
            classification.requested_information,
            debug_metadata["db_called"],
            debug_metadata["rag_called"],
            structured_evidence_pack.get("selected_evidence_count", 0),
            debug_metadata["gemini_called"],
            answer_source,
            {
                "route_family": route_family,
                "fallback_reason": debug_metadata["fallback_reason"],
                "formatter_mode": debug_metadata["formatter_mode"],
            },
        )
        answer, output_pii = mask_pii(answer)

        top_score = grouped[0].best_score if grouped else 0.0
        combined_score = composite_confidence(
            top_score, reranker_score, classification.confidence
        )
        assistant = Message(
            conversation_id=conversation.id,
            role="ASSISTANT",
            safe_content=answer,
            category=classification.category,
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
            security_metadata=self._json_safe(
                {
                    "output_pii_masked": output_pii,
                    "pipeline_errors": pipeline_errors,
                    "debug": {
                        "route_family": route_family,
                        "router": self._router_payload(classification),
                        "db_called": debug_metadata["db_called"],
                        "rag_called": debug_metadata["rag_called"],
                        "selected_evidence_count": structured_evidence_pack.get(
                            "selected_evidence_count", 0
                        ),
                        "gemini_called": debug_metadata["gemini_called"],
                        "gemini_polish_used": gemini_polish_used,
                        "answer_source": answer_source,
                        "fallback_reason": debug_metadata["fallback_reason"],
                        "formatter_mode": debug_metadata["formatter_mode"],
                    },
                }
            ),
        )
        logger.info(
            "pipeline_trace trace_id=%s router_provider_used=%s fallback_used=%s domain=%s intent=%s category=%s subcategory=%s requested_information=%s db_needed=%s rag_needed=%s db_called=%s rag_called=%s product_candidates=%s order_candidates=%s return_candidates=%s selected_evidence_count=%s gemini_called=%s answer_source=%s raw_context_dump=%s",
            self.current_trace_id,
            getattr(self.classifier, "last_provider", classification.provider),
            getattr(self.classifier, "last_fallback_used", False),
            classification.domain,
            classification.intent,
            classification.category,
            classification.subcategory,
            ",".join(classification.requested_information or ([] if not classification.requested_info else [classification.requested_info])),
            bool(context_plan.data_sources),
            bool(context_plan.needs_support_rag),
            pipeline_fetches_context,
            bool(grouped),
            debug_metadata.get("product_context", {}).get("selected_counts", {}).get("products", 0),
            debug_metadata.get("customer_context", {}).get("selected_counts", {}).get("orders", 0),
            debug_metadata.get("customer_context", {}).get("selected_counts", {}).get("returns", 0),
            structured_evidence_pack.get("selected_evidence_count", 0),
            debug_metadata["gemini_called"],
            answer_source,
            False,
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
            last_topic=classification.category,
            last_product_id=product_context.get("primary_product", {}).get("id"),
            last_product_name=product_context.get("primary_product", {}).get("name", ""),
            last_order_id=product_context.get("primary_order", {}).get("id"),
            last_order_no=product_context.get("primary_order", {}).get("order_no", ""),
            last_return_id=product_context.get("primary_return", {}).get("id"),
            last_cart_id=product_context.get("primary_cart", {}).get("id")
            or frontend_context.get("current_cart_id"),
            last_payment_id=product_context.get("primary_payment", {}).get("id")
            or frontend_context.get("current_payment_id"),
            last_intent=classification.intent or product_context.get("route_mode", ""),
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
                "route_mode": route_family,
                "support_category": classification.category,
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
                retrieval_results=self._json_safe(assistant.sources),
                customer_context=self._json_safe({
                    "support": support_context,
                    "product": product_context,
                }),
                few_shot_examples=self._json_safe(few_shots),
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
                classification_result=self._json_safe(
                    {
                        **classification.as_dict(),
                        "context_resolver": context_plan_metadata,
                        "data_resolver": data_resolution_metadata,
                        "evidence_fetcher": evidence_metadata,
                    }
                ),
            )
        )
        if conversation.title == "Yeni görüşme":
            conversation.title = canonical[:255]
        trace_elapsed["total"] = round((time.perf_counter() - started) * 1000, 2)
        trace_elapsed.setdefault("gemini", 0.0)
        trace.set("elapsed_ms", trace_elapsed)
        final_metadata = {
            "answer_source": answer_source,
            "formatter_mode": debug_metadata["formatter_mode"],
            "fallback_reason": debug_metadata["fallback_reason"],
            "gemini_polish_used": gemini_polish_used,
            "elapsed_ms": trace_elapsed,
            "category": classification.category,
            "subcategory": classification.subcategory,
            "expected_action": classification.expected_action,
            "priority": classification.priority,
            "confidence": confidence_label(combined_score, self.settings),
            "confidence_score": combined_score,
            "sources": assistant.sources,
            "pipeline_errors": pipeline_errors,
            "final_answer": answer,
            "final_answer_preview": answer[:1200],
        }
        trace.set("final", final_metadata)
        trace.add_stage("final_answer", final_metadata)
        await session.commit()
        await session.refresh(assistant)
        trace_elapsed["total"] = round((time.perf_counter() - started) * 1000, 2)
        final_metadata["elapsed_ms"] = trace_elapsed
        trace.set("elapsed_ms", trace_elapsed)
        trace.set("final", final_metadata)
        trace.write()
        return assistant, canonical, grouped, similar, classification
