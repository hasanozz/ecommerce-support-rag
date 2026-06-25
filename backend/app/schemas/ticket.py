from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TicketResponse(BaseModel):
    id: int
    conversation_id: int
    source_message_id: int
    category: str
    department: str
    status: str
    user_note: str
    admin_note: str
    created_at: datetime
    updated_at: datetime


class AdminTicketUpdate(BaseModel):
    status: Literal["OPEN", "IN_REVIEW", "RESOLVED"]
    admin_note: str = Field(default="", max_length=1000)


class TicketCreateRequest(BaseModel):
    note: str = Field(default="", max_length=1000)
