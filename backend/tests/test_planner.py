"""Tests for study planner API endpoints."""

import json
import pytest
from unittest.mock import MagicMock
from datetime import date, timedelta
import uuid as uuid_mod

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.api.deps import get_current_user
from app.models.profile import Profile
from app.models.planner import StudyPlan, StudyTask, PlanStatus, TaskStatus
from app.models.document import Document, DocumentStatus


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
