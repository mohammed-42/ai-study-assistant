from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    subject_id: UUID
    name: str = Field(..., min_length=1, max_length=500)
    doc_type: str = Field(default="pdf", pattern="^(pdf|image|multi_image)$")


class DocumentOut(BaseModel):
    id: UUID
    owner_id: UUID
    subject_id: UUID
    name: str
    doc_type: str
    status: str
    page_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)


class DocumentPageOut(BaseModel):
    id: UUID
    document_id: UUID
    page_number: int
    text: str
    source: str
    needs_review: bool
    user_edited: bool
    page_image_key: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkOut(BaseModel):
    id: UUID
    document_id: UUID
    page_start: int
    page_end: int
    content: str
    token_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
