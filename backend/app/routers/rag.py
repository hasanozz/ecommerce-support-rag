from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.rag import (
    ChatRequest,
    ChatResponse,
    GroupedSearchResult,
    SearchRequest,
    SearchResponse,
    Source,
)
from ..services.chat import ChatService
from ..services.retrieval import RetrievalService
from ..services.security import sanitize_query


router = APIRouter(tags=["rag"])


@router.post("/rag/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest, session: AsyncSession = Depends(get_db)
) -> SearchResponse:
    query = sanitize_query(payload.query)
    grouped_results = await RetrievalService().grouped_search(
        session,
        query,
        candidate_limit=max(payload.limit, 20),
        max_documents=3,
        max_sections=6,
    )
    return SearchResponse(
        query=query,
        grouped_results=[
            GroupedSearchResult(
                doc_id=document.doc_id,
                title=document.title,
                category=document.category,
                subcategory=document.subcategory,
                best_score=document.best_score,
                matched_sections=document.matched_sections,
                combined_context=document.combined_context,
            )
            for document in grouped_results
        ],
        llm_context="\n\n====================\n\n".join(
            document.combined_context for document in grouped_results
        ),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest, session: AsyncSession = Depends(get_db)
) -> ChatResponse:
    query = sanitize_query(payload.message)
    answer, chunks, confidence = await ChatService().answer(session, query)
    return ChatResponse(
        answer=answer,
        sources=[
            Source(
                doc_id=chunk.doc_id,
                title=chunk.title,
                section=chunk.section,
                score=chunk.score,
            )
            for chunk in chunks
        ],
        confidence=confidence,
    )
