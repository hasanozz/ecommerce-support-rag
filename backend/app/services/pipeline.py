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
from .gemini import GeminiService, GeminiServiceError, guard_llm_output
from .ai_contracts import ContextBuilder, PassthroughReranker
from .classifier import ClassificationResult, ClassifierService
from .confidence import composite_confidence, confidence_label
from .demo_commerce import CustomerContextService
from .privacy import mask_pii
from .retrieval import GroupedDocument, RetrievalService
from .similar import SimilarSolutionService


ORDER_NO_PATTERN = re.compile(r"\bDMO-[A-Za-z0-9-]+\b", re.IGNORECASE)
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
        self.customer_context = CustomerContextService()
        self.reranker = PassthroughReranker()
        self.context_builder = ContextBuilder()

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
        if any(hint in normalized for hint in FOLLOWUP_HINTS):
            return True
        return False

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
    ) -> str:
        customer_text = (customer_context or {}).get("text", "").strip()
        customer_items = (customer_context or {}).get("items", [])
        customer_category = (customer_context or {}).get("category", "")
        if customer_text:
            if customer_category == "KARGO_TESLIMAT":
                formatted_items = [
                    self._format_customer_context_item(item) for item in customer_items
                ]
                if len(customer_items) == 1:
                    return (
                        "Kargonuzun son durumu şu şekilde görünüyor:\n"
                        f"- {formatted_items[0]}"
                    )
                return (
                    "Hesabınızda kargo bilgisi olan birden fazla demo sipariş görünüyor. "
                    "Son durumları aşağıda listeliyorum; hangi sipariş için işlem yapmak "
                    "istediğinizi sipariş numarasıyla yazabilirsiniz:\n"
                    + "\n".join(f"- {item}" for item in formatted_items)
                )
            return (
                "Hesabınızdaki demo işlem bilgileri şu şekilde görünüyor:\n"
                + "\n".join(
                    f"- {self._format_customer_context_item(item)}"
                    for item in customer_items
                )
            )
        if not grouped:
            return (
                "Bu soruya mevcut bilgi tabanında yeterince güvenilir bir yanıt "
                "bulamadım. Lütfen sorununuzla ilgili biraz daha ayrıntı verin."
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
            return standard_chunk
        document = await session.get(Document, grouped[0].doc_id)
        if document:
            standard = document.raw_json.get("standart_yanit", "")
            if standard and "?" not in standard:
                return standard
        return grouped[0].combined_context[:1500]

    def _format_customer_context_item(self, item: str) -> str:
        match = re.match(r"Sipariş\s+(DMO-[^:]+):\s*(.+)\.?$", item.strip())
        if not match:
            return item
        order_no, detail_text = match.groups()
        details: dict[str, str] = {}
        for part in detail_text.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            details[key.strip()] = value.strip().rstrip(".")
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

    async def run(
        self,
        session: AsyncSession,
        conversation: Conversation,
        user: User,
        safe_query: str,
        ip_hash: str,
    ) -> tuple[
        Message,
        str,
        list[GroupedDocument],
        list[tuple[object, float, int]],
        ClassificationResult,
    ]:
        started = time.perf_counter()
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
                .limit(4)
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
            },
        )
        session.add(user_message)
        await session.flush()

        in_scope = bool(rewrite.get("is_in_scope", True)) and (
            classification.expected_action != "REJECT"
        )
        customer_context = (
            await self.customer_context.build(
                session,
                user,
                category,
                canonical,
                selected_order_no=followup_reference.get("order_no"),
            )
            if in_scope
            else {"category": category, "items": [], "text": ""}
        )
        grouped = []
        if in_scope:
            try:
                grouped = await self.retrieval.grouped_search(
                    session,
                    canonical,
                    candidate_limit=30,
                    max_documents=3,
                    max_sections=6,
                )
            except HTTPException:
                pipeline_errors.append("RETRIEVAL_UNAVAILABLE")
        if in_scope and not grouped and customer_context.get("text"):
            try:
                grouped = await self.retrieval.grouped_by_category(
                    session,
                    category,
                    max_documents=3,
                    max_sections=6,
                )
            except HTTPException:
                pipeline_errors.append("CATEGORY_RETRIEVAL_UNAVAILABLE")
        grouped, reranker_score = await self.reranker.rerank(canonical, grouped)
        if grouped and category == "GENEL_DESTEK":
            category = grouped[0].category
            user_message.category = category

        similar = (
            await self.similar.search(session, canonical, category, limit=3)
            if in_scope
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
        generated = {"answer": "", "cited_doc_ids": []}
        answer_usage: dict = {}
        if in_scope and (grouped or customer_context.get("text")):
            try:
                generated = await self.gemini.answer(
                    canonical,
                    history,
                    customer_context.get("text", ""),
                    llm_context,
                    few_shots,
                    use_dev_model=True,
                )
                answer_usage = dict(self.gemini.last_usage)
            except GeminiServiceError:
                pipeline_errors.append("GEMINI_ANSWER_UNAVAILABLE")
        cited_ids = set(generated.get("cited_doc_ids", []))
        allowed_ids = {item.doc_id for item in grouped}
        answer = guard_llm_output(
            generated.get("answer", ""),
            allowed_ids,
        )
        if cited_ids and not cited_ids.issubset(allowed_ids):
            answer = ""
        if classification.expected_action == "ASK_CLARIFICATION":
            answer = (
                "Sorununuzu doğru yönlendirebilmem için hangi sipariş, ödeme, "
                "iade veya teslimat durumuyla ilgili olduğunu biraz daha açıklar mısınız?"
            )
        elif not in_scope:
            answer = "Bu asistan yalnızca e-ticaret müşteri destek konularını yanıtlar."
        elif not answer:
            answer = await self._fallback_answer(session, grouped, customer_context)
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
        session.add(
            RagRun(
                assistant_message_id=assistant.id,
                rewritten_query=canonical,
                retrieval_results=assistant.sources,
                customer_context=customer_context,
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
                classification_result=classification.as_dict(),
            )
        )
        if conversation.title == "Yeni görüşme":
            conversation.title = canonical[:255]
        await session.commit()
        await session.refresh(assistant)
        return assistant, canonical, grouped, similar, classification
