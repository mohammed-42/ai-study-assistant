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


class ChatMessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    citation_ids: list[str] | None
    is_insufficient: bool
    created_at: datetime

    model_config = {"from_attributes": True}
    
    @classmethod
    def from_orm(cls, obj) -> "ChatMessageOut":
        data = {
            "id": obj.id,
            "session_id": obj.session_id,
            "role": obj.role,
            "content": obj.content,
            "is_insufficient": obj.is_insufficient,
            "created_at": obj.created_at,
        }
        if obj.citation_ids:
            try:
                data["citation_ids"] = json.loads(obj.citation_ids)
            except (json.JSONDecodeError, TypeError):
                data["citation_ids"] = []
        else:
            data["citation_ids"] = None
        return cls(**data)


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    session_id: UUID | None = None
    # Optional filters for retrieval
    subject_id: UUID | None = None
    document_ids: list[UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0)
