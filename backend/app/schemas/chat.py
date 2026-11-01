from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    subject_id: UUID | None = None
    title: str = Field(default="New Chat", max_length=500)


class ChatSessionOut(BaseModel):
    id: UUID
    owner_id: UUID
    subject_id: UUID | None
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CitationOut(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page_start: int
    page_end: int
    is_ocr: bool
    needs_review: bool
    user_edited: bool
    has_unverified_ocr: bool

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    citations: list[CitationOut] | None = None
    is_insufficient: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    session_id: UUID | None = None
    # Optional filters for retrieval
    subject_id: UUID | None = None
    document_ids: list[UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0)
