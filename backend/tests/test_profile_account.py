"""Tests for profile editing and account deletion (mocked storage/Supabase)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_current_user
from app.main import app
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.note import Note
from app.models.planner import StudyPlan, StudyTask
from app.models.processing_job import ProcessingJob
from app.models.profile import Profile
from app.models.quiz import Quiz, QuizAttempt, QuizQuestion, QuizResponse
from app.models.subject import Subject


@pytest.fixture
def client(db_session, test_user):
    mock_user = MagicMock()
    mock_user.id = test_user.id
    mock_user.sub = test_user.sub
    mock_user.email = test_user.email

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


async def _seed_user_data(db_session, user, subject):
    doc = Document(
        owner_id=user.id,
        subject_id=subject.id,
        name="account.pdf",
        doc_type="pdf",
        status=DocumentStatus.READY,
        storage_key=f"user/{user.id}/doc/account.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    page = DocumentPage(document_id=doc.id, page_number=1, text="page text")
    chunk = DocumentChunk(
        document_id=doc.id,
        page_start=1,
        page_end=1,
        content="chunk text",
        token_count=2,
        embedding=[0.1] * 768,
    )
    job = ProcessingJob(document_id=doc.id)
    db_session.add_all([page, chunk, job])

    note = Note(
        owner_id=user.id,
        subject_id=subject.id,
        document_id=doc.id,
        title="note",
        note_type="summary",
        content="note content",
    )
    session = ChatSession(owner_id=user.id, subject_id=subject.id, title="chat")
    db_session.add_all([note, session])
    await db_session.commit()
    await db_session.refresh(session)

    message = ChatMessage(session_id=session.id, role="user", content="hello")
    db_session.add(message)

    quiz = Quiz(
        owner_id=user.id,
        subject_id=subject.id,
        document_id=doc.id,
        title="quiz",
        question_count=1,
    )
    db_session.add(quiz)
    await db_session.commit()
    await db_session.refresh(quiz)

    question = QuizQuestion(
        quiz_id=quiz.id,
        question_text="question?",
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
        user_id=user.id,
        total_questions=1,
        correct_answers=1,
        score=100,
    )
    db_session.add(attempt)
    await db_session.commit()
    await db_session.refresh(attempt)

    response = QuizResponse(
        attempt_id=attempt.id,
        question_id=question.id,
        selected_option_index=0,
        is_correct=True,
    )
    db_session.add(response)

    plan = StudyPlan(
        owner_id=user.id,
        subject_id=subject.id,
        exam_date=date.today() + timedelta(days=7),
        title="plan",
        daily_minutes=30,
        preferred_days="mon",
        topics=json.dumps(["topic"]),
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    task = StudyTask(
        plan_id=plan.id,
        topic="task",
        importance=5,
        scheduled_days="mon",
        scheduled_date=date.today(),
        estimated_minutes=30,
    )
    db_session.add(task)
    await db_session.commit()

    return {
        "doc": doc,
        "page": page,
        "chunk": chunk,
        "job": job,
        "note": note,
        "session": session,
        "message": message,
        "quiz": quiz,
        "question": question,
        "attempt": attempt,
        "response": response,
        "plan": plan,
        "task": task,
    }


@pytest.mark.asyncio
async def test_get_profile_returns_current_user(db_session, test_user, client):
    response = client.get("/api/profile")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["email"] == test_user.email
    assert data["full_name"] == "Test User"


@pytest.mark.asyncio
async def test_update_profile_is_owner_only(db_session, test_user, client):
    other = Profile(sub="other-sub", email="other@example.com", full_name="Other")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    response = client.put(
        "/api/profile",
        json={"full_name": "  Updated Name  ", "email": "hacked@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"
    assert response.json()["email"] == test_user.email

    await db_session.refresh(test_user)
    await db_session.refresh(other)
    assert test_user.full_name == "Updated Name"
    assert test_user.email == "test@example.com"
    assert other.full_name == "Other"
    assert other.email == "other@example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"full_name": ""}, {"full_name": "   "}, {"full_name": "x" * 256}])
async def test_update_profile_rejects_invalid_full_name(client, payload):
    response = client.put("/api/profile", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_account_cascades_and_leaves_other_users_alone(
    db_session, test_user, test_subject, client, monkeypatch
):
    other = Profile(sub="other-sub", email="other@example.com", full_name="Other")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    other_subject = Subject(owner_id=other.id, name="Other Subject")
    db_session.add(other_subject)
    await db_session.commit()
    await db_session.refresh(other_subject)
    other_note = Note(owner_id=other.id, title="other note", content="keep")
    db_session.add(other_note)
    await db_session.commit()

    seeded = await _seed_user_data(db_session, test_user, test_subject)
    user_id = test_user.id
    user_sub = test_user.sub
    subject_id = test_subject.id
    other_id = other.id
    other_subject_id = other_subject.id
    other_note_id = other_note.id
    seeded_ids = {key: value.id for key, value in seeded.items()}

    calls: list[tuple[str, str]] = []

    def fake_storage(owner_id):
        calls.append(("storage", str(owner_id)))
        return 3

    def fake_auth(sub):
        calls.append(("auth", sub))

    monkeypatch.setattr("app.api.profile.delete_user_objects", fake_storage)
    monkeypatch.setattr("app.api.profile.delete_auth_user", fake_auth)

    response = client.delete("/api/account")

    assert response.status_code == 204
    assert calls == [("storage", str(user_id)), ("auth", user_sub)]

    db_session.expire_all()
    assert (await db_session.execute(
        select(Profile).where(Profile.id == user_id)
    )).scalar_one_or_none() is None
    assert (await db_session.execute(
        select(Subject).where(Subject.id == subject_id)
    )).scalar_one_or_none() is None

    for key, model in [
        ("doc", Document),
        ("page", DocumentPage),
        ("chunk", DocumentChunk),
        ("job", ProcessingJob),
        ("note", Note),
        ("session", ChatSession),
        ("message", ChatMessage),
        ("quiz", Quiz),
        ("question", QuizQuestion),
        ("attempt", QuizAttempt),
        ("response", QuizResponse),
        ("plan", StudyPlan),
        ("task", StudyTask),
    ]:
        row = await db_session.get(model, seeded_ids[key])
        assert row is None, key

    assert (await db_session.get(Profile, other_id)) is not None
    assert (await db_session.get(Subject, other_subject_id)) is not None
    assert (await db_session.get(Note, other_note_id)) is not None


@pytest.mark.asyncio
async def test_delete_account_storage_failure_reports_and_keeps_account(
    db_session, test_user, client, monkeypatch
):
    auth_calls = []

    def fail_storage(owner_id):
        raise RuntimeError("storage down")

    monkeypatch.setattr("app.api.profile.delete_user_objects", fail_storage)
    monkeypatch.setattr(
        "app.api.profile.delete_auth_user", lambda sub: auth_calls.append(sub)
    )

    response = client.delete("/api/account")

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Account not deleted" in detail
    assert "stored files" in detail
    assert auth_calls == []
    assert (await db_session.get(Profile, test_user.id)) is not None


@pytest.mark.asyncio
async def test_delete_account_auth_failure_reports_partial_state(
    db_session, test_user, client, monkeypatch
):
    storage_calls = []
    user_id = test_user.id

    def fake_storage(owner_id):
        storage_calls.append(owner_id)
        return 0

    def fail_auth(sub):
        raise RuntimeError("auth down")

    monkeypatch.setattr("app.api.profile.delete_user_objects", fake_storage)
    monkeypatch.setattr("app.api.profile.delete_auth_user", fail_auth)

    response = client.delete("/api/account")

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "data and stored files were deleted" in detail
    assert "login account could not be removed" in detail
    assert storage_calls == [user_id]
    db_session.expire_all()
    assert (await db_session.get(Profile, user_id)) is None
