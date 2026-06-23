from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from .retrieval import GroupedDocument


class Rewriter(Protocol):
    async def rewrite(self, safe_query: str, history: list[str]) -> dict: ...


class Retriever(Protocol):
    async def grouped_search(
        self,
        session: AsyncSession,
        query: str,
        *,
        candidate_limit: int = 30,
        max_documents: int = 3,
        max_sections: int = 6,
    ) -> list[GroupedDocument]: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: list[GroupedDocument]
    ) -> tuple[list[GroupedDocument], float | None]: ...


class PassthroughReranker:
    """TODO: RAG geliştiricisi gerçek cross-encoder reranker adapterını bağlayacak."""

    async def rerank(
        self, query: str, documents: list[GroupedDocument]
    ) -> tuple[list[GroupedDocument], float | None]:
        del query
        return documents, None


class ContextBuilder:
    @staticmethod
    def build(documents: list[GroupedDocument]) -> str:
        return "\n\n====================\n\n".join(
            item.combined_context for item in documents[:3]
        )
