from typing import Literal

from pydantic import BaseModel, Field


class MessageFeedbackRequest(BaseModel):
    value: Literal["HELPFUL", "UNHELPFUL"]
    open_ticket: bool = False
    note: str = Field(default="", max_length=1000)


class SimilarFeedbackRequest(BaseModel):
    value: Literal["HELPFUL", "UNHELPFUL"]


class FeedbackResponse(BaseModel):
    status: str
    ticket_id: int | None = None
