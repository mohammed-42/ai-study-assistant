"""Cross-user isolation tests for all user-owned resources (mocked/SQLite)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.rate_limit import rate_limiter
from app.main import app
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.note import Note
from app.models.planner import StudyPlan, StudyTask
from app.models.profile import Profile
from app.models.quiz import Quiz, QuizAttempt, QuizQuestion


@pytest.fixture
def client(db_session):
    rate_limiter.reset()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        rate_limiter.reset()


@pytest.fixture
async def user_b(db_session):
    user = Profile(sub="isolation-user-b", email="isolation-b@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _act_as(user) -> None:
    mock = MagicMock()
    mock.id = user.id
    mock.email = user.email
    app.dependency_overrides[get_current_user] = lambda: mock


async def _seed_document(db_session, owner, subject):
    doc = Document(
        owner_id=owner.id,
        subject_id=subject.id,
        name="owner-a.pdf",
        doc_type="pdf",
        status=DocumentStatus.READY,
        storage_key=f"user/{owner.id}/doc/owner-a.pdf",
        page_count=1,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text="Owner A private page text.",
        source="ocr",
        page_image_key=f"user/{owner.id}/{doc.id}/0.png",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    chunk = DocumentChunk(
        document_id=doc.id,
        page_start=1,
        page_end=1,
        content="Owner A private chunk text.",
        token_count=8,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk)
    await db_session.commit()
    await db_session.refresh(chunk)
    return doc, page, chunk


@pytest.mark.asyncio
async def test_documents_pages_chunks_and_page_actions_are_isolated(
    db_session, test_user, test_subject, user_b, client
):
    doc, page, _chunk = await _seed_document(db_session, test_user, test_subject)

    _act_as(user_b)
    assert client.get("/api/documents/").json() == []
    assert client.get(f"/api/documents/{doc.id}").status_code == 404
    assert client.get(f"/api/documents/{doc.id}/pages").status_code == 404
    assert client.get(f"/api/documents/{doc.id}/chunks").status_code == 404
    assert (
        client.get(f"/api/documents/{doc.id}/pages/{page.id}/image-url").status_code
        == 404
    )
    assert (
        client.put(
            f"/api/documents/{doc.id}/pages/{page.id}",
            json={"text": "tampered by B", "user_edited": True},
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/documents/{doc.id}/pages/{page.id}/rerun-ocr").status_code
        == 404
    )
    assert client.delete(f"/api/documents/{doc.id}").status_code == 404

    _act_as(test_user)
    assert client.get(f"/api/documents/{doc.id}").status_code == 200
    assert client.get(f"/api/documents/{doc.id}/pages").json()[0]["text"] == (
        "Owner A private page text."
    )


@pytest.mark.asyncio
async def test_chat_sessions_and_messages_are_isolated(
    db_session, test_user, user_b, client
):
    session = ChatSession(owner_id=test_user.id, title="Owner A session")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    message = ChatMessage(session_id=session.id, role="user", content="Owner A message")
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)

    _act_as(user_b)
    assert client.get("/api/chat/sessions").json() == []
    assert client.get(f"/api/chat/sessions/{session.id}/messages").status_code == 404
    assert (
        client.post(
            f"/api/chat/sessions/{session.id}/messages",
            json={"content": "B injection"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/chat/sessions/{session.id}").status_code == 404

    _act_as(test_user)
    assert len(client.get("/api/chat/sessions").json()) == 1
    assert len(client.get(f"/api/chat/sessions/{session.id}/messages").json()) == 1


@pytest.mark.asyncio
async def test_notes_are_isolated(db_session, test_user, user_b, client):
    note = Note(
        owner_id=test_user.id,
        title="Owner A note",
        note_type="summary",
        content="Owner A private note.",
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    _act_as(user_b)
    assert client.get("/api/notes").json() == []
    assert client.get(f"/api/notes/{note.id}").status_code == 404
    assert (
        client.put(f"/api/notes/{note.id}", json={"title": "tampered"}).status_code
        == 404
    )
    assert client.delete(f"/api/notes/{note.id}").status_code == 404

    _act_as(test_user)
    assert client.get(f"/api/notes/{note.id}").json()["content"] == (
        "Owner A private note."
    )


@pytest.mark.asyncio
async def test_quizzes_and_attempts_are_isolated(
    db_session, test_user, user_b, client
):
    quiz = Quiz(owner_id=test_user.id, title="Owner A quiz", question_count=1)
    db_session.add(quiz)
    await db_session.commit()
    await db_session.refresh(quiz)
    question = QuizQuestion(
        quiz_id=quiz.id,
        question_text="Owner A question?",
        question_type="mcq",
        options=json.dumps(["a", "b"]),
        correct_option_index=0,
        order=0,
    )
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(question)
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=test_user.id,
        total_questions=1,
        correct_answers=1,
        score=100,
    )
    db_session.add(attempt)
    await db_session.commit()
    await db_session.refresh(attempt)

    _act_as(user_b)
    assert client.get("/api/quizzes").json() == []
    assert client.get(f"/api/quizzes/{quiz.id}").status_code == 404
    assert client.get(f"/api/quizzes/{quiz.id}/attempts").status_code == 404
    assert client.get(f"/api/quizzes/{quiz.id}/summary").status_code == 404
    assert (
        client.post(
            f"/api/quizzes/{quiz.id}/submit",
            json={
                "responses": [
                    {"question_id": str(question.id), "selected_option_index": 0}
                ]
            },
        ).status_code
        == 404
    )
    assert client.delete(f"/api/quizzes/{quiz.id}").status_code == 404

    _act_as(test_user)
    assert client.get(f"/api/quizzes/{quiz.id}").status_code == 200
    assert len(client.get(f"/api/quizzes/{quiz.id}/attempts").json()) == 1


@pytest.mark.asyncio
async def test_study_plans_and_tasks_are_isolated(
    db_session, test_user, user_b, client
):
    plan = StudyPlan(
        owner_id=test_user.id,
        exam_date=date.today() + timedelta(days=7),
        title="Owner A plan",
        daily_minutes=60,
        preferred_days="mon,tue",
        topics=json.dumps(["algebra"]),
        status="active",
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    task = StudyTask(
        plan_id=plan.id,
        topic="Owner A task",
        importance=5,
        scheduled_days="mon",
        scheduled_date=date.today(),
        status="pending",
        estimated_minutes=30,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    _act_as(user_b)
    assert client.get("/api/planner/plans").json() == []
    assert client.get(f"/api/planner/plans/{plan.id}").status_code == 404
    assert (
        client.put(
            f"/api/planner/plans/{plan.id}", json={"title": "tampered"}
        ).status_code
        == 404
    )
    assert client.post(f"/api/planner/plans/{plan.id}/generate").status_code == 404
    assert client.post(f"/api/planner/plans/{plan.id}/regenerate").status_code == 404
    assert client.delete(f"/api/planner/plans/{plan.id}").status_code == 404
    assert (
        client.put(f"/api/planner/tasks/{task.id}", json={"status": "completed"})
        .status_code
        == 404
    )
    assert client.delete(f"/api/planner/tasks/{task.id}").status_code == 404

    dashboard = client.get("/api/planner/dashboard").json()
    assert dashboard["today_pending_tasks"] == 0
    assert dashboard["today_tasks_summary"] == []
    assert dashboard["active_plans_count"] == 0
    assert dashboard["plan_progress"]["total"] == 0
    assert dashboard["weak_topics"] == []

    _act_as(test_user)
    assert client.get(f"/api/planner/plans/{plan.id}").status_code == 200
    assert client.get(f"/api/planner/plans/{plan.id}").json()["title"] == (
        "Owner A plan"
    )


AUTH_PATHS = [
    "/api/subjects/",
    "/api/documents/",
    "/api/chat/sessions",
    "/api/notes",
    "/api/quizzes",
    "/api/planner/plans",
    "/api/planner/dashboard",
]


@pytest.mark.parametrize("path", AUTH_PATHS)
def test_unauthenticated_requests_get_401(path):
    app.dependency_overrides.clear()
    client = TestClient(app)
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", AUTH_PATHS)
def test_garbage_token_requests_get_401(path, monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setattr(
        "app.api.deps._get_jwks", AsyncMock(return_value={"keys": []})
    )
    client = TestClient(app)
    response = client.get(path, headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
