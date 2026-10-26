"""Study planner API endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.planner import StudyPlan, PlanStatus, StudyTask, TaskStatus
from app.models.profile import Profile
from app.models.subject import Subject
from app.models.quiz import QuizAttempt, Quiz
from app.schemas.planner import PlanCreate, PlanOut, PlanUpdate, TaskOut, TaskUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/planner", tags=["planner"])


# --- Plan CRUD ---

@router.get("/plans", response_model=list[dict])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    stmt = (
        select(StudyPlan)
        .where(StudyPlan.owner_id == user.id)
        .order_by(StudyPlan.exam_date.asc())
    )
    result = await db.execute(stmt)
    plans = result.scalars().all()
    return [_plan_to_dict(p) for p in plans]


@router.post("/plans", response_model=PlanOut, status_code=201)
async def create_plan(
    body: PlanCreate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    if body.subject_id:
        subj = await db.execute(
            select(Subject).where(Subject.id == body.subject_id, Subject.owner_id == user.id)
        )
        if subj.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")

    plan = StudyPlan(
        owner_id=user.id,
        subject_id=body.subject_id,
        title=body.title,
        exam_date=body.exam_date,
        daily_minutes=body.daily_minutes,
        preferred_days=body.preferred_days_str,
        topics=body.topics_str,
        status=PlanStatus.ACTIVE,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return _plan_to_out(plan)


@router.get("/plans/{plan_id}", response_model=dict)
async def get_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    plan = await _get_owner_plan(db, uuid.UUID(plan_id), user.id)
    task_result = await db.execute(
        select(StudyTask).where(StudyTask.plan_id == plan.id).order_by(StudyTask.scheduled_date)
    )
    tasks = task_result.scalars().all()
    return {
        **_plan_to_dict(plan),
        "tasks": [_task_to_dict(t) for t in tasks],
    }


@router.put("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: str,
    body: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    plan = await _get_owner_plan(db, uuid.UUID(plan_id), user.id)
    if body.title is not None:
        plan.title = body.title
    if body.exam_date is not None:
        plan.exam_date = body.exam_date
    if body.daily_minutes is not None:
        plan.daily_minutes = body.daily_minutes
    if body.preferred_days is not None:
        plan.preferred_days = ",".join(body.preferred_days)
    if body.topics is not None:
        plan.topics = json.dumps(body.topics)
    if body.status is not None:
        plan.status = PlanStatus(body.status)
    await db.commit()
    await db.refresh(plan)
    return _plan_to_out(plan)


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    plan = await _get_owner_plan(db, uuid.UUID(plan_id), user.id)
    # Explicitly delete tasks (SQLite doesn't enforce FK CASCADE at ORM level)
    await db.execute(select(StudyTask).where(StudyTask.plan_id == plan.id))
    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(StudyTask).where(StudyTask.plan_id == plan.id))
    await db.delete(plan)
    await db.commit()
    return None


# --- Generate schedule ---

@router.post("/plans/{plan_id}/generate", response_model=list[TaskOut])
async def generate_schedule(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    from app.services.planner import generate_schedule

    plan = await _get_owner_plan(db, uuid.UUID(plan_id), user.id)
    task_result = await db.execute(
        select(StudyTask).where(StudyTask.plan_id == plan.id)
    )
    existing_tasks = task_result.scalars().all()

    # Get quiz avg for this subject (if provided)
    quiz_avg: float | None = None
    if plan.subject_id:
        avg_result = await db.execute(
            select(QuizAttempt.score)
            .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
            .where(Quiz.subject_id == plan.subject_id, QuizAttempt.user_id == user.id)
        )
        scores = [r for r in avg_result.scalars().all() if r is not None]
        if scores:
            quiz_avg = sum(scores) / len(scores)

    try:
        new_tasks = generate_schedule(plan, existing_tasks, quiz_avg)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Only insert truly new tasks
    inserted = []
    for task in new_tasks:
        if task.id is None:
            db.add(task)
            inserted.append(task)
    if inserted:
        await db.commit()
        for t in inserted:
            await db.refresh(t)

    result = await db.execute(
        select(StudyTask).where(StudyTask.plan_id == plan.id).order_by(StudyTask.scheduled_date)
    )
    return [TaskOut.from_orm(t) for t in result.scalars().all()]


# --- Regenerate (preserves completed) ---

@router.post("/plans/{plan_id}/regenerate", response_model=list[TaskOut])
async def regenerate_schedule(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    from app.services.planner import regenerate_plan

    plan = await _get_owner_plan(db, uuid.UUID(plan_id), user.id)
    task_result = await db.execute(
        select(StudyTask).where(StudyTask.plan_id == plan.id)
    )
    existing_tasks = task_result.scalars().all()

    quiz_avg: float | None = None
    if plan.subject_id:
        avg_result = await db.execute(
            select(QuizAttempt.score)
            .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
            .where(Quiz.subject_id == plan.subject_id, QuizAttempt.user_id == user.id)
        )
        scores = [r for r in avg_result.scalars().all() if r is not None]
        if scores:
            quiz_avg = sum(scores) / len(scores)

    try:
        new_tasks = regenerate_plan(plan, existing_tasks, quiz_avg)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    inserted = []
    for task in new_tasks:
        if task.id is None:
            db.add(task)
            inserted.append(task)
    if inserted:
        await db.commit()
        for t in inserted:
            await db.refresh(t)

    result = await db.execute(
        select(StudyTask).where(StudyTask.plan_id == plan.id).order_by(StudyTask.scheduled_date)
    )
    return [TaskOut.from_orm(t) for t in result.scalars().all()]


# --- Task CRUD ---

@router.put("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    task = await _get_owner_task(db, uuid.UUID(task_id), user.id)
    if body.status is not None:
        task.status = TaskStatus(body.status)
        if body.status == TaskStatus.COMPLETED and task.completed_at is None:
            task.completed_at = task.completed_at or task.created_at
    if body.actual_minutes is not None:
        task.actual_minutes = body.actual_minutes
    await db.commit()
    await db.refresh(task)
    return TaskOut.from_orm(task)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    task = await _get_owner_task(db, uuid.UUID(task_id), user.id)
    await db.delete(task)
    await db.commit()
    return None


# --- Dashboard stats ---

@router.get("/dashboard", response_model=dict)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Return computed dashboard stats from real data."""
    from app.models.document import Document, DocumentStatus
    from app.models.note import Note
    from app.models.quiz import QuizAttempt

    # Document counts by status
    doc_stmt = select(Document.status, func.count(Document.id)).where(
        Document.owner_id == user.id
    ).group_by(Document.status)
    doc_result = await db.execute(doc_stmt)
    doc_by_status = {s.value if hasattr(s, 'value') else s: c for s, c in doc_result.all()}

    # Recent notes count
    note_stmt = select(func.count(Note.id)).where(
        Note.owner_id == user.id,
        Note.created_at >= date.today() - timedelta(days=7)
    )
    recent_notes = (await db.execute(note_stmt)).scalar() or 0

    # Recent quiz attempts
    attempt_stmt = (
        select(QuizAttempt.score, QuizAttempt.created_at)
        .where(QuizAttempt.user_id == user.id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(5)
    )
    attempts = await db.execute(attempt_stmt)
    recent_quizzes = [
        {"score": a.score, "date": a.created_at.isoformat()}
        for a in attempts.scalars().all()
    ]

    # Active plans and today's tasks
    today = date.today()
    plan_stmt = select(StudyPlan).where(
        StudyPlan.owner_id == user.id,
        StudyPlan.status == PlanStatus.ACTIVE
    )
    active_plans = (await db.execute(plan_stmt)).scalars().all()

    task_stmt = select(StudyTask).where(
        StudyTask.scheduled_date == today,
        StudyTask.status == TaskStatus.PENDING,
        StudyTask.plan_id.in_(
            select(StudyPlan.id).where(StudyPlan.owner_id == user.id)
        ),
    )
    today_tasks_result = await db.execute(task_stmt)
    today_tasks = today_tasks_result.scalars().all()

    # Overall progress
    all_plan_tasks_stmt = select(StudyTask).where(
        StudyTask.plan_id.in_([p.id for p in active_plans])
    ) if active_plans else select(StudyTask).where(False)
    all_tasks = (await db.execute(all_plan_tasks_stmt)).scalars().all()
    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED)
    progress_pct = round(completed / total * 100) if total > 0 else 0

    # Weak topics (from quiz performance)
    weak_topics_stmt = (
        select(StudyTask.topic, func.avg(QuizAttempt.score))
        .outerjoin(QuizAttempt, StudyTask.plan_id == StudyPlan.id)
        .where(StudyPlan.owner_id == user.id)
        .group_by(StudyTask.topic)
        .having(func.avg(QuizAttempt.score) < 50)
        .limit(5)
    )
    # Simpler: just top pending topics by importance
    weak_stmt = (
        select(StudyTask.topic, StudyTask.importance)
        .where(
            StudyTask.plan_id.in_([p.id for p in active_plans]),
            StudyTask.status == TaskStatus.PENDING,
        )
        .order_by(StudyTask.importance.desc())
        .limit(5)
    )
    weak_result = await db.execute(weak_stmt)
    weak_topics = [{"topic": r.topic, "importance": r.importance} for r in weak_result.all()]

    return {
        "document_counts": doc_by_status,
        "recent_notes": recent_notes,
        "recent_quizzes": recent_quizzes,
        "active_plans_count": len(active_plans),
        "today_pending_tasks": len(today_tasks),
        "today_tasks_summary": [
            {"id": str(t.id), "topic": t.topic, "estimated_minutes": t.estimated_minutes}
            for t in today_tasks[:5]
        ],
        "plan_progress": {"total": total, "completed": completed, "percentage": progress_pct},
        "weak_topics": weak_topics,
    }


# --- Helpers ---

def _plan_to_dict(plan: StudyPlan) -> dict:
    return {
        "id": str(plan.id),
        "owner_id": str(plan.owner_id),
        "subject_id": str(plan.subject_id) if plan.subject_id else None,
        "exam_date": plan.exam_date.isoformat(),
        "title": plan.title,
        "daily_minutes": plan.daily_minutes,
        "preferred_days": [d.strip() for d in plan.preferred_days.split(",") if d.strip()],
        "topics": json.loads(plan.topics) if plan.topics else [],
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }


def _plan_to_out(plan: StudyPlan) -> PlanOut:
    return PlanOut.from_orm(plan)


def _task_to_dict(task: StudyTask) -> dict:
    return {
        "id": str(task.id),
        "plan_id": str(task.plan_id),
        "topic": task.topic,
        "importance": task.importance,
        "scheduled_days": [d.strip() for d in task.scheduled_days.split(",") if d.strip()] if task.scheduled_days else [],
        "scheduled_date": task.scheduled_date.isoformat() if task.scheduled_date else None,
        "status": task.status,
        "estimated_minutes": task.estimated_minutes,
        "actual_minutes": task.actual_minutes,
        "reason": task.reason,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


async def _get_owner_plan(db: AsyncSession, plan_id: uuid.UUID, owner_id: uuid.UUID) -> StudyPlan:
    stmt = select(StudyPlan).where(StudyPlan.id == plan_id, StudyPlan.owner_id == owner_id)
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan not found or not owned")
    return plan


async def _get_owner_task(db: AsyncSession, task_id: uuid.UUID, owner_id: uuid.UUID) -> StudyTask:
    plan_stmt = select(StudyPlan).where(StudyPlan.id == StudyTask.plan_id, StudyPlan.owner_id == owner_id)
    # We need to join through
    from sqlalchemy import and_
    stmt = select(StudyTask).join(
        StudyPlan, StudyTask.plan_id == StudyPlan.id
    ).where(
        StudyTask.id == task_id,
        StudyPlan.owner_id == owner_id,
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found or not owned")
    return task
