from __future__ import annotations

import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from ..config import Settings, get_settings
from ..models import Chunk, Conversation, Document, Message, RagRun
from .gemini import GeminiService, GeminiServiceError, guard_llm_output
from .ai_contracts import ContextBuilder, PassthroughReranker
from .classifier import ClassificationResult, ClassifierService
from .confidence import composite_confidence, confidence_label
from .privacy import mask_pii
from .retrieval import GroupedDocument, RetrievalService
from .similar import SimilarSolutionService


class SupportPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.gemini = GeminiService(self.settings)
        self.rewriter = self.gemini
        self.retrieval = RetrievalService()
        self.similar = SimilarSolutionService(settings=self.settings)
        self.classifier = ClassifierService(self.settings)
        self.reranker = PassthroughReranker()
        self.context_builder = ContextBuilder()

    async def _fallback_answer(
        self, session: AsyncSession, grouped: list[GroupedDocument]
    ) -> str:
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

    async def run(
        self,
        session: AsyncSession,
        conversation: Conversation,
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
        classification = await self.classifier.classify(safe_query, masked_query)
        classifier_usage = dict(self.classifier.last_usage)
        history = (
            await session.scalars(
                select(Message.safe_content)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.id.desc())
                .limit(4)
            )
        ).all()
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
                    list(reversed(history)),
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
        category = classification.category or rewrite.get("category", "GENEL_DESTEK")

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
        if in_scope and grouped:
            try:
                generated = await self.gemini.answer(
                    canonical,
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
            answer = await self._fallback_answer(session, grouped)
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
