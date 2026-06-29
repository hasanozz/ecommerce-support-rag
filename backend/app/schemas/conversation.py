from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="Yeni görüşme", max_length=255)


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    current_product_id: int | None = Field(default=None, ge=1)
    current_order_id: int | None = Field(default=None, ge=1)
    current_cart_id: int | None = Field(default=None, ge=1)
    current_return_id: int | None = Field(default=None, ge=1)
    current_payment_id: int | None = Field(default=None, ge=1)
    page_context: Literal[
        "shop",
        "product",
        "cart",
        "orders",
        "returns",
        "favorites",
        "scenarios",
        "tickets",
        "history",
        "admin",
        "admin-demo",
    ] | None = None


class SourceResponse(BaseModel):
    doc_id: str
    title: str
    category: str
    subcategory: str
    best_score: float
    matched_sections: list[str]
    combined_context: str


class SimilarSolutionResponse(BaseModel):
    id: int
    canonical_question: str
    safe_answer: str
    similarity_score: float
    helpful_count: int
    view_count: int
    success_rate: float


class AssistantAnswerResponse(BaseModel):
    assistant_message_id: int
    answer: str
    canonical_query: str
    sources: list[SourceResponse]
    confidence: Literal["HIGH", "MEDIUM", "LOW"] | None
    confidence_score: float | None
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
    similar_solutions: list[SimilarSolutionResponse]
    ticket_available: bool = True
    ticket_recommended: bool = False


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    canonical_query: str | None
    category: str | None
    confidence: str | None
    sources: list[dict]
    helpful_count: int
    unhelpful_count: int
    user_feedback: Literal["HELPFUL", "UNHELPFUL"] | None = None
    created_at: datetime


class ConversationSummary(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageResponse]
