"""Tests for study planner API endpoints."""

import json
import pytest
from unittest.mock import MagicMock
from datetime import date, datetime, timedelta
import uuid as uuid_mod

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.api.deps import get_current_user
from app.models.profile import Profile
from app.models.planner import StudyPlan, StudyTask, PlanStatus, TaskStatus
from app.models.document import Document, DocumentStatus
from app.models.quiz import Quiz, QuizAttempt


@pytest.fixture
def client(db_session, test_user):
    mock_user = MagicMock()
    mock_user.id = test_user.id
    mock_user.email = test_user.email
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


async def _create_plan(db_session, **overrides):
    exam = overrides.pop("exam_date", date.today() + timedelta(days=10))
    plan = StudyPlan(
        owner_id=overrides.pop("owner_id"),
        title=overrides.pop("title", "Plan"),
        exam_date=exam,
        daily_minutes=overrides.pop("daily_minutes", 60),
        preferred_days=overrides.pop("preferred_days", "mon,tue,wed,thu,fri"),
        topics=json.dumps(overrides.pop("topics", ["A"])),
        status=PlanStatus.ACTIVE,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


async def _create_task(db_session, plan, **overrides):
    task = StudyTask(
        plan_id=plan.id,
        topic=overrides.get("topic", "A"),
        importance=overrides.get("importance", 5),
        scheduled_days="mon",
        status=TaskStatus.PENDING,
        estimated_minutes=overrides.get("estimated_minutes", 30),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


class TestPlanCreate:
    @pytest.mark.asyncio
    async def test_create_plan(self, client, test_user, db_session):
        exam = date.today() + timedelta(days=30)
        payload = {
            "title": "Final Exam",
            "exam_date": exam.isoformat(),
            "daily_minutes": 60,
            "preferred_days": ["mon", "tue", "wed"],
            "topics": ["Algebra", "Calculus"],
        }
        resp = client.post("/api/planner/plans", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == "Final Exam"
        assert data["exam_date"] == exam.isoformat()
        assert data["topics"] == ["Algebra", "Calculus"]
        assert data["daily_minutes"] == 60
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_plan_requires_title(self, client):
        resp = client.post("/api/planner/plans", json={"topics": ["A"]})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_plan_unauthenticated(self, client):
        app.dependency_overrides.clear()
        resp = client.post("/api/planner/plans", json={
            "title": "Exam",
            "exam_date": (date.today() + timedelta(days=30)).isoformat(),
            "topics": ["A"],
        })
        assert resp.status_code in (401, 403)


class TestPlanListOwnership:
    @pytest.mark.asyncio
    async def test_list_plans_ownership_isolation(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        resp = client.get("/api/planner/plans")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_list_plans_empty(self, client):
        resp = client.get("/api/planner/plans")
        assert resp.status_code == 200
        assert resp.json() == []


class TestPlanGet:
    @pytest.mark.asyncio
    async def test_get_plan(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        resp = client.get(f"/api/planner/plans/{plan.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Plan"

    @pytest.mark.asyncio
    async def test_get_plan_not_found(self, client):
        fake = str(uuid_mod.uuid4())
        resp = client.get(f"/api/planner/plans/{fake}")
        assert resp.status_code == 404


class TestPlanUpdate:
    @pytest.mark.asyncio
    async def test_update_plan_title(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        resp = client.put(f"/api/planner/plans/{plan.id}", json={"title": "New"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    @pytest.mark.asyncio
    async def test_update_plan_status(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        resp = client.put(f"/api/planner/plans/{plan.id}", json={"status": "paused"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    @pytest.mark.asyncio
    async def test_update_plan_invalid_status(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        resp = client.put(f"/api/planner/plans/{plan.id}", json={"status": "invalid"})
        assert resp.status_code == 422


class TestPlanDelete:
    @pytest.mark.asyncio
    async def test_delete_plan(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        resp = client.delete(f"/api/planner/plans/{plan.id}")
        assert resp.status_code == 204

        # Verify gone
        resp2 = client.get(f"/api/planner/plans/{plan.id}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_plan_cascades_tasks(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        await _create_task(db_session, plan)
        client.delete(f"/api/planner/plans/{plan.id}")

        result = await db_session.execute(select(StudyTask).where(StudyTask.plan_id == plan.id))
        assert result.scalars().first() is None


class TestGenerateSchedule:
    @pytest.mark.asyncio
    async def test_generate_schedule_creates_tasks(self, client, test_user, db_session):
        exam = date.today() + timedelta(days=14)
        plan = await _create_plan(db_session, owner_id=test_user.id, exam_date=exam, topics=["Topic A", "Topic B"])
        resp = client.post(f"/api/planner/plans/{plan.id}/generate")
        assert resp.status_code == 200, resp.text
        tasks = resp.json()
        assert len(tasks) >= 2
        topics = {t["topic"] for t in tasks}
        assert "Topic A" in topics
        assert "Topic B" in topics

    @pytest.mark.asyncio
    async def test_generate_schedule_rejects_past_exam(self, client, test_user, db_session):
        past = date.today() - timedelta(days=1)
        plan = await _create_plan(db_session, owner_id=test_user.id, exam_date=past)
        resp = client.post(f"/api/planner/plans/{plan.id}/generate")
        assert resp.status_code == 400


class TestRegenerateSchedule:
    @pytest.mark.asyncio
    async def test_regenerate_preserves_completed_and_removes_duplicates(
        self, client, test_user, db_session
    ):
        exam = date.today() + timedelta(days=14)
        plan = await _create_plan(
            db_session,
            owner_id=test_user.id,
            exam_date=exam,
            topics=["Topic A", "Topic B"],
        )
        resp = client.post(f"/api/planner/plans/{plan.id}/generate")
        assert resp.status_code == 200, resp.text
        tasks = resp.json()
        assert len(tasks) >= 2

        done = tasks[0]
        resp = client.put(
            f"/api/planner/tasks/{done['id']}", json={"status": "completed"}
        )
        assert resp.status_code == 200, resp.text

        resp = client.post(f"/api/planner/plans/{plan.id}/regenerate")
        assert resp.status_code == 200, resp.text
        regenerated = resp.json()

        assert any(
            t["id"] == done["id"] and t["status"] == "completed"
            for t in regenerated
        )
        pending = [t["topic"] for t in regenerated if t["status"] != "completed"]
        assert len(pending) == len(set(pending))

        result = await db_session.execute(
            select(StudyTask).where(StudyTask.plan_id == plan.id)
        )
        db_pending = [
            t.topic
            for t in result.scalars().all()
            if t.status != TaskStatus.COMPLETED
        ]
        assert len(db_pending) == len(set(db_pending))


class TestTaskUpdate:
    @pytest.mark.asyncio
    async def test_update_task_status(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        task = await _create_task(db_session, plan)
        resp = client.put(f"/api/planner/tasks/{task.id}", json={"status": "completed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_task_actual_minutes(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        task = await _create_task(db_session, plan)
        resp = client.put(f"/api/planner/tasks/{task.id}", json={"actual_minutes": 45})
        assert resp.status_code == 200
        assert resp.json()["actual_minutes"] == 45

    @pytest.mark.asyncio
    async def test_delete_task(self, client, test_user, db_session):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        task = await _create_task(db_session, plan)
        resp = client.delete(f"/api/planner/tasks/{task.id}")
        assert resp.status_code == 204

        result = await db_session.execute(select(StudyTask).where(StudyTask.id == task.id))
        assert result.scalars().first() is None


class TestDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_returns_stats(self, client, test_user, db_session):
        resp = client.get("/api/planner/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "document_counts" in data
        assert "active_plans_count" in data
        assert "plan_progress" in data
        assert isinstance(data["active_plans_count"], int)

    @pytest.mark.asyncio
    async def test_dashboard_counts_documents(self, client, test_user, db_session, test_subject):
        doc = Document(
            owner_id=test_user.id, subject_id=test_subject.id, name="Test.pdf",
            doc_type="pdf", status=DocumentStatus.READY, page_count=5,
        )
        db_session.add(doc)
        await db_session.commit()

        resp = client.get("/api/planner/dashboard")
        data = resp.json()
        assert data["document_counts"].get("ready", 0) >= 1

    @pytest.mark.asyncio
    async def test_dashboard_upcoming_exams_nearest_first(
        self, client, test_user, db_session
    ):
        today = date.today()
        await _create_plan(
            db_session, owner_id=test_user.id, title="Far",
            exam_date=today + timedelta(days=9),
        )
        await _create_plan(
            db_session, owner_id=test_user.id, title="Near",
            exam_date=today + timedelta(days=2),
        )
        await _create_plan(
            db_session, owner_id=test_user.id, title="Past",
            exam_date=today - timedelta(days=3),
        )

        data = client.get("/api/planner/dashboard").json()
        assert [e["title"] for e in data["upcoming_exams"]] == ["Near", "Far"]
        assert [e["days_left"] for e in data["upcoming_exams"]] == [2, 9]

    @pytest.mark.asyncio
    async def test_dashboard_today_tasks_include_status(
        self, client, test_user, db_session
    ):
        plan = await _create_plan(db_session, owner_id=test_user.id)
        today = date.today()
        for topic, status in [("Pending task", TaskStatus.PENDING), ("Done task", TaskStatus.COMPLETED)]:
            db_session.add(
                StudyTask(
                    plan_id=plan.id, topic=topic, importance=5,
                    scheduled_days="mon", scheduled_date=today,
                    status=status, estimated_minutes=30,
                )
            )
        await db_session.commit()

        data = client.get("/api/planner/dashboard").json()
        by_topic = {t["topic"]: t for t in data["today_tasks"]}
        assert by_topic["Pending task"]["status"] == "pending"
        assert by_topic["Done task"]["status"] == "completed"
        assert data["today_pending_tasks"] == 1

    @pytest.mark.asyncio
    async def test_dashboard_recent_documents_last_five(
        self, client, test_user, db_session, test_subject
    ):
        base = datetime(2026, 1, 1, 12, 0, 0)
        for i in range(6):
            db_session.add(
                Document(
                    owner_id=test_user.id, subject_id=test_subject.id,
                    name=f"Doc {i}.pdf", doc_type="pdf",
                    status=DocumentStatus.READY, page_count=1,
                    created_at=base + timedelta(minutes=i),
                )
            )
        await db_session.commit()

        data = client.get("/api/planner/dashboard").json()
        names = [d["name"] for d in data["recent_documents"]]
        assert names == ["Doc 5.pdf", "Doc 4.pdf", "Doc 3.pdf", "Doc 2.pdf", "Doc 1.pdf"]
        assert data["recent_documents"][0]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_dashboard_recent_quizzes_include_title(
        self, client, test_user, db_session
    ):
        quiz = Quiz(owner_id=test_user.id, title="Algebra quiz", question_count=2)
        db_session.add(quiz)
        await db_session.commit()
        await db_session.refresh(quiz)
        for i, score in enumerate([100, 50]):
            db_session.add(
                QuizAttempt(
                    quiz_id=quiz.id, user_id=test_user.id, score=score,
                    total_questions=2, correct_answers=score // 50,
                    created_at=datetime(2026, 1, 1, 12, i, 0),
                )
            )
        await db_session.commit()

        data = client.get("/api/planner/dashboard").json()
        assert len(data["recent_quizzes"]) == 2
        assert data["recent_quizzes"][0]["quiz_title"] == "Algebra quiz"
        assert data["recent_quizzes"][0]["quiz_id"] == str(quiz.id)
        assert data["recent_quizzes"][0]["score"] == 50

    @pytest.mark.asyncio
    async def test_dashboard_recent_lists_exclude_other_users(
        self, client, test_user, db_session, test_subject
    ):
        other = Profile(sub="other-dash", email="other-dash@example.com")
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)

        db_session.add(
            Document(
                owner_id=other.id, subject_id=test_subject.id,
                name="Other.pdf", doc_type="pdf",
                status=DocumentStatus.READY, page_count=1,
            )
        )
        quiz = Quiz(owner_id=other.id, title="Other quiz", question_count=1)
        db_session.add(quiz)
        await db_session.commit()
        await db_session.refresh(quiz)
        db_session.add(
            QuizAttempt(
                quiz_id=quiz.id, user_id=other.id, score=90,
                total_questions=1, correct_answers=1,
            )
        )
        await db_session.commit()

        data = client.get("/api/planner/dashboard").json()
        assert data["recent_documents"] == []
        assert data["recent_quizzes"] == []
