from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Chunk
from .embedding import EmbeddingService, get_embedding_service


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    title: str
    category: str
    subcategory: str
    section: str
    content: str
    contextual_content: str
    score: float


@dataclass(slots=True)
class GroupedDocument:
    doc_id: str
    title: str
    category: str
    subcategory: str
    best_score: float
    matched_sections: list[str]
    combined_context: str


SECTION_LABELS = {
    "amac": "Amaç",
    "kapsam": "Kapsam",
    "tanim": "Tanım",
    "genel_bilgiler": "Genel Bilgiler",
    "kosullar": "Koşullar",
    "adimlar": "Adımlar",
    "istisnalar": "İstisnalar",
    "surec": "Süreç",
    "standart_yanit": "Standart Yanıt",
}
SECTION_ORDER = {
    "tanim": 0,
    "kapsam": 1,
    "kosullar": 2,
    "genel_bilgiler": 3,
    "adimlar": 4,
    "istisnalar": 5,
    "surec": 6,
    "standart_yanit": 7,
    "amac": 8,
}
CATEGORY_LABELS = {
    "SIPARIS": "Sipariş",
    "IADE": "İade",
    "ODEME": "Ödemeler",
    "KARGO_TESLIMAT": "Kargo / Teslimat",
    "HESAP_GUVENLIK": "Hesap ve Kullanıcı Güvenliği",
    "KAMPANYA_PUAN": "Kampanya ve Puan",
}


def _base_section(section: str) -> str:
    for name in SECTION_LABELS:
        if section == name or section.startswith(f"{name}_"):
            return name
    return section


def group_chunks(
    chunks: list[RetrievedChunk],
    *,
    max_documents: int = 3,
    max_sections: int = 6,
    min_score: float = 0.0,
) -> list[GroupedDocument]:
    grouped: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.doc_id, []).append(chunk)

    documents: list[GroupedDocument] = []
    for doc_chunks in grouped.values():
        best_score = max(chunk.score for chunk in doc_chunks)
        section_scores: dict[str, float] = {}
        section_contents: dict[str, list[str]] = {}
        for chunk in doc_chunks:
            section = _base_section(chunk.section)
            section_scores[section] = max(section_scores.get(section, 0.0), chunk.score)
            contents = section_contents.setdefault(section, [])
            if chunk.content not in contents:
                contents.append(chunk.content)

        selected_sections = sorted(
            section_contents,
            key=lambda section: (
                -section_scores[section],
                SECTION_ORDER.get(section, 99),
            ),
        )[:max_sections]
        selected_sections.sort(key=lambda section: SECTION_ORDER.get(section, 99))

        first = doc_chunks[0]
        context_parts = [
            f"Doküman: {first.title}",
            f"Kategori: {CATEGORY_LABELS.get(first.category, first.category)}",
        ]
        for section in selected_sections:
            label = SECTION_LABELS.get(section, section.replace("_", " ").title())
            content = "\n".join(section_contents[section])
            context_parts.append(f"{label}:\n{content}")

        documents.append(
            GroupedDocument(
                doc_id=first.doc_id,
                title=first.title,
                category=first.category,
                subcategory=first.subcategory,
                best_score=round(best_score, 4),
                matched_sections=selected_sections,
                combined_context="\n\n".join(context_parts),
            )
        )

    documents.sort(key=lambda document: document.best_score, reverse=True)
    return [
        document
        for document in documents
        if document.best_score >= min_score
    ][:max_documents]


class RetrievalService:
    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or get_embedding_service()

    async def search(
        self, session: AsyncSession, query: str, limit: int = 10
    ) -> list[RetrievedChunk]:
        query_vector = self.embedding_service.embed_query(query)
        distance = Chunk.embedding.cosine_distance(query_vector)
        statement = (
            select(Chunk, distance.label("distance"))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await session.execute(statement)).all()
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                title=chunk.title,
                category=chunk.category,
                subcategory=chunk.subcategory,
                section=chunk.section,
                content=chunk.content,
                contextual_content=chunk.contextual_content,
                score=round(max(0.0, min(1.0, 1.0 - float(row_distance))), 4),
            )
            for chunk, row_distance in rows
        ]

    async def grouped_search(
        self,
        session: AsyncSession,
        query: str,
        *,
        candidate_limit: int = 30,
        max_documents: int = 3,
        max_sections: int = 6,
    ) -> list[GroupedDocument]:
        chunks = await self.search(session, query, limit=candidate_limit)
        return group_chunks(
            chunks,
            max_documents=max_documents,
            max_sections=max_sections,
            min_score=self.embedding_service.settings.min_retrieval_score,
        )
