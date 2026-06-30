from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MessageFeedbackRequest(BaseModel):
    value: Literal["HELPFUL", "UNHELPFUL"]
    open_ticket: bool = False
    comment: str | None = Field(default=None, max_length=1000)
    note: str = Field(default="", max_length=1000)


class SimilarFeedbackRequest(BaseModel):
    value: Literal["HELPFUL", "UNHELPFUL"]


class FeedbackResponse(BaseModel):
    status: str
    ticket_id: int | None = None


class FeedbackCategoryBreakdown(BaseModel):
    category: str
    helpful_count: int
    unhelpful_count: int
    total: int
    helpful_rate: float


class RecentFeedbackItem(BaseModel):
    message_id: int
    ai_answer: str
    canonical_query: str | None
    category: str | None
    confidence_score: float | None
    sources: list[dict]
    feedback_value: Literal["HELPFUL", "UNHELPFUL"]
    feedback_comment: str | None = None
    feedback_created_at: datetime
    user_id: int
    model_name: str | None = None
    total_tokens: int | None = None


class FeedbackAnalyticsResponse(BaseModel):
    total_feedback: int
    helpful_count: int
    unhelpful_count: int
    helpful_rate: float
    unhelpful_rate: float
    average_confidence_score: float | None
    category_breakdown: list[FeedbackCategoryBreakdown]
    recent_feedback: list[RecentFeedbackItem]
