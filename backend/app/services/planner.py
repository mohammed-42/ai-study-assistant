"""Rule-based study planner — schedules tasks without AI."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from uuid import UUID

from app.models.planner import StudyPlan
from app.models.planner import StudyTask, TaskStatus

logger = logging.getLogger(__name__)

DAY_MAP = {
    "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7,
}
REVERSE_DAY_MAP = {v: k for k, v in DAY_MAP.items()}


def _importance_score(topic: str, exam_date: date, tasks: list[StudyTask], quiz_avg: float | None) -> int:
    """Compute importance score for a topic (1–10)."""
    # Base importance from topic length heuristic
    base = min(10, max(1, len(topic) // 10))

    # Quiz performance adjustment — lower avg → higher priority
    if quiz_avg is not None:
        if quiz_avg < 40:
            base = min(10, base + 4)
        elif quiz_avg < 60:
            base = min(10, base + 2)
        elif quiz_avg >= 80:
            base = max(1, base - 2)

    # Topics with no completed tasks get a boost
    completed_topics = {t.topic.lower() for t in tasks if t.status == TaskStatus.COMPLETED}
    if topic.lower() not in completed_topics:
        base = min(10, base + 2)

    return base


def generate_schedule(
    plan: StudyPlan,
    existing_tasks: list[StudyTask],
    quiz_avg: float | None = None,
) -> list[StudyTask]:
    """Generate study tasks for a plan using rule-based scheduling.

    Rules:
    - Never schedule after exam_date
    - Distribute topics across available days
    - Higher importance → more frequent / earlier scheduling
    - Preserve completed tasks; regenerate only pending/in-progress
    - Daily time budget respected
    """
    today = date.today()
    exam = plan.exam_date

    if exam <= today:
        raise ValueError("Exam date must be in the future")

    total_days = (exam - today).days
    if total_days == 0:
        raise ValueError("Exam is today — no schedule to generate")

    daily_budget = plan.daily_minutes
    preferred = [d.strip() for d in plan.preferred_days.split(",") if d.strip()]
    if not preferred:
        preferred = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    preferred_offsets = {DAY_MAP.get(d, 1) for d in preferred}

    # Parse topics
    topics = json.loads(plan.topics) if isinstance(plan.topics, str) else plan.topics
    if not topics:
        return []

    # Separate existing tasks by status
    completed = [t for t in existing_tasks if t.status == TaskStatus.COMPLETED]
    pending = [t for t in existing_tasks if t.status != TaskStatus.COMPLETED]
    pending_topics = {t.topic for t in pending}

    # Determine which topics still need scheduling
    unscheduled_topics = [t for t in topics if t not in pending_topics]
    if not unscheduled_topics:
        return existing_tasks

    # Compute importance for each unscheduled topic
    topic_scores = []
    for topic in unscheduled_topics:
        imp = _importance_score(topic, exam, existing_tasks, quiz_avg)
        topic_scores.append((topic, imp))

    # Sort by importance descending
    topic_scores.sort(key=lambda x: -x[1])

    # Distribute across days
    new_tasks: list[StudyTask] = []
    # Track minutes per day
    daily_minutes = {}

    # Generate dates: from today to exam-1, on preferred days
    all_dates = []
    current = today
    while current < exam:
        weekday = current.weekday() + 1  # mon=1 ... sun=7
        if weekday in preferred_offsets:
            all_dates.append(current)
        current += timedelta(days=1)

    if not all_dates:
        raise ValueError("No suitable study days between today and exam date")

    # Allocate topics to dates, respecting daily budget
    tasks_per_day = max(1, len(all_dates) // max(1, len(unscheduled_topics)))
    task_index = 0
    date_index = 0

    while task_index < len(topic_scores) and date_index < len(all_dates):
        topic, importance = topic_scores[task_index]
        study_date = all_dates[date_index]
        date_str = study_date.isoformat()

        # Estimate minutes: importance * 5, capped at daily budget
        est_minutes = min(importance * 5, daily_budget // max(1, len([t for t in new_tasks if t.scheduled_date == study_date]) + 1))
        est_minutes = max(15, est_minutes)

        # Check daily budget
        used = daily_minutes.get(date_str, 0)
        if used + est_minutes > daily_budget:
            # Move to next day
            date_index += 1
            continue

        daily_minutes[date_str] = used + est_minutes

        reason = _build_reason(topic, importance, exam, quiz_avg)

        new_tasks.append(StudyTask(
            plan_id=plan.id,
            topic=topic,
            importance=importance,
            scheduled_days=plan.preferred_days,
            scheduled_date=study_date,
            status=TaskStatus.PENDING,
            estimated_minutes=est_minutes,
            reason=reason,
        ))

        task_index += 1
        # Move to next date if we've filled this one or batch done
        if task_index % tasks_per_day == 0 or task_index >= len(topic_scores):
            date_index += 1

    return existing_tasks + new_tasks


def _build_reason(topic: str, importance: int, exam_date: date, quiz_avg: float | None) -> str:
    """Plain-language reason for why this topic is scheduled."""
    days_to_exam = (exam_date - date.today()).days
    parts = [f"{importance}/10 importance"]
    if quiz_avg is not None:
        if quiz_avg < 50:
            parts.append(f"low quiz performance ({int(quiz_avg)}%)")
        elif quiz_avg >= 80:
            parts.append(f"strong performance ({int(quiz_avg)}%)")
    parts.append(f"{days_to_exam} days until exam")
    return "Priority: " + ", ".join(parts) + "."


def regenerate_plan(
    plan: StudyPlan,
    existing_tasks: list[StudyTask],
    quiz_avg: float | None = None,
) -> list[StudyTask]:
    """Regenerate schedule, preserving completed tasks."""
    today = date.today()
    completed = [t for t in existing_tasks if t.status == TaskStatus.COMPLETED]
    completed_dates = {t.scheduled_date for t in completed if t.scheduled_date}
    completed_topics = {t.topic for t in completed}

    # Parse topics
    topics = json.loads(plan.topics) if isinstance(plan.topics, str) else plan.topics

    # Topics still needing work
    remaining = [t for t in topics if t not in completed_topics]
    if not remaining:
        return completed

    # Re-run scheduling, excluding completed dates and topics
    daily_budget = plan.daily_minutes
    preferred = [d.strip() for d in plan.preferred_days.split(",") if d.strip()]
    preferred_offsets = {DAY_MAP.get(d, 1) for d in preferred}

    topic_scores = []
    for topic in remaining:
        imp = _importance_score(topic, plan.exam_date, completed, quiz_avg)
        topic_scores.append((topic, imp))
    topic_scores.sort(key=lambda x: -x[1])

    all_dates = []
    current = today
    while current < plan.exam_date:
        if current not in completed_dates:
            weekday = current.weekday() + 1
            if weekday in preferred_offsets:
                all_dates.append(current)
        current += timedelta(days=1)

    if not all_dates:
        return completed + [
            StudyTask(plan_id=plan.id, topic=t, importance=s, scheduled_days=plan.preferred_days,
                      scheduled_date=None, status=TaskStatus.PENDING, estimated_minutes=30,
                      reason="No available study days — adjust plan dates.")
            for t, s in topic_scores
        ]

    tasks_per_day = max(1, len(all_dates) // max(1, len(topic_scores)))
    new_tasks: list[StudyTask] = []
    daily_minutes: dict[str, int] = {}
    task_index = 0
    date_index = 0

    while task_index < len(topic_scores) and date_index < len(all_dates):
        topic, importance = topic_scores[task_index]
        study_date = all_dates[date_index]
        date_str = study_date.isoformat()
        est_minutes = min(importance * 5, daily_budget // max(1, len([t for t in new_tasks if t.scheduled_date == study_date]) + 1))
        est_minutes = max(15, est_minutes)

        used = daily_minutes.get(date_str, 0)
        if used + est_minutes > daily_budget:
            date_index += 1
            continue

        daily_minutes[date_str] = used + est_minutes
        reason = _build_reason(topic, importance, plan.exam_date, quiz_avg)

        new_tasks.append(StudyTask(
            plan_id=plan.id,
            topic=topic,
            importance=importance,
            scheduled_days=plan.preferred_days,
            scheduled_date=study_date,
            status=TaskStatus.PENDING,
            estimated_minutes=est_minutes,
            reason=reason,
        ))
        task_index += 1
        if task_index % tasks_per_day == 0 or task_index >= len(topic_scores):
            date_index += 1

    return completed + new_tasks
