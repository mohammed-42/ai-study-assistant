from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    subject_id: UUID | None = None
    document_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    note_type: str = Field(default="summary", pattern="^(summary|key_concepts|definitions|revision)$")
    content: str = Field(..., min_length=1)


class NoteOut(BaseModel):
    id: UUID
    owner_id: UUID
    subject_id: UUID | None
    document_id: UUID | None
    title: str
    note_type: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    note_type: str | None = Field(None, pattern="^(summary|key_concepts|definitions|revision)$")
    content: str | None = Field(None, min_length=1)
