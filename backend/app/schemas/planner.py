from __future__ import annotations

import json
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    subject_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    exam_date: date
    daily_minutes: int = Field(default=60, ge=15, le=480)
    preferred_days: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])
    topics: list[str] = Field(..., min_length=1)

    @property
    def preferred_days_str(self) -> str:
        return ",".join(self.preferred_days)

    @property
    def topics_str(self) -> str:
        return json.dumps(self.topics)


class PlanOut(BaseModel):
    id: UUID
    owner_id: UUID
    subject_id: UUID | None
    exam_date: date
    title: str
    daily_minutes: int
    preferred_days: list[str]
    topics: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        data = {
            "id": obj.id,
            "owner_id": obj.owner_id,
            "subject_id": obj.subject_id,
            "exam_date": obj.exam_date,
            "title": obj.title,
            "daily_minutes": obj.daily_minutes,
            "preferred_days": [d.strip() for d in obj.preferred_days.split(",") if d.strip()],
            "topics": json.loads(obj.topics) if obj.topics else [],
            "status": obj.status,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)


class PlanUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    exam_date: date | None = None
    daily_minutes: int | None = Field(None, ge=15, le=480)
    preferred_days: list[str] | None = None
    topics: list[str] | None = None
    status: str | None = Field(None, pattern="^(active|completed|paused)$")


class TaskOut(BaseModel):
    id: UUID
    plan_id: UUID
    topic: str
    importance: int
    scheduled_days: list[str]
    scheduled_date: date | None
    status: str
    estimated_minutes: int
    actual_minutes: int | None
    reason: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        data = {
            "id": obj.id,
            "plan_id": obj.plan_id,
            "topic": obj.topic,
            "importance": obj.importance,
            "scheduled_days": [d.strip() for d in obj.scheduled_days.split(",") if d.strip()] if obj.scheduled_days else [],
            "scheduled_date": obj.scheduled_date,
            "status": obj.status,
            "estimated_minutes": obj.estimated_minutes,
            "actual_minutes": obj.actual_minutes,
            "reason": obj.reason,
            "created_at": obj.created_at,
            "completed_at": obj.completed_at,
        }
        return cls(**data)


class TaskUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(pending|in_progress|completed)$")
    actual_minutes: int | None = Field(None, ge=0)
