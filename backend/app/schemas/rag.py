from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=30)


class GroupedSearchResult(BaseModel):
    doc_id: str
    title: str
    category: str
    subcategory: str
    best_score: float
    matched_sections: list[str]
    combined_context: str


class SearchResponse(BaseModel):
    query: str
    grouped_results: list[GroupedSearchResult]
    llm_context: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class Source(BaseModel):
    doc_id: str
    title: str
    section: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
