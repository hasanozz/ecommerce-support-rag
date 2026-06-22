from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..models import QueryLog
from .llm import AnswerService
from .retrieval import RetrievedChunk, RetrievalService


class ChatService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.retrieval = RetrievalService()
        self.answer_service = AnswerService(self.settings)

    @staticmethod
    def confidence(score: float) -> str:
        if score >= 0.78:
            return "HIGH"
        if score >= 0.62:
            return "MEDIUM"
        return "LOW"

    async def answer(
        self, session: AsyncSession, query: str
    ) -> tuple[str, list[RetrievedChunk], str]:
        chunks = await self.retrieval.search(
            session, query, limit=self.settings.search_limit
        )
        top_score = chunks[0].score if chunks else 0.0
        confidence = self.confidence(top_score)
        if not chunks or top_score < self.settings.min_retrieval_score:
            answer = (
                "Bu soruya mevcut bilgi tabanında yeterince güvenilir bir yanıt "
                "bulamadım. Lütfen sipariş, ödeme, iade, kargo veya hesap işleminizle "
                "ilgili daha fazla ayrıntı verin."
            )
            used_chunks: list[RetrievedChunk] = []
        else:
            used_chunks = chunks[:5]
            answer = await self.answer_service.generate(query, used_chunks)

        session.add(
            QueryLog(
                user_query=query,
                rewritten_query=None,
                retrieved_chunks=[
                    {
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "section": chunk.section,
                        "score": chunk.score,
                    }
                    for chunk in used_chunks
                ],
                final_answer=answer,
            )
        )
        await session.commit()
        return answer, used_chunks, confidence
