from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlanStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    preferred_days: Mapped[str] = mapped_column(String(50), nullable=False, default="mon,tue,wed,thu,fri")
    # JSON list of topic strings
    topics: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[PlanStatus] = mapped_column(
        String(20), nullable=False, default=PlanStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), index=True
    )
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # 1-7 representing days of week (mon=1 ... sun=7)
    scheduled_days: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        String(20), nullable=False, default=TaskStatus.PENDING
    )
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
