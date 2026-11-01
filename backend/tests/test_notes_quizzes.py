"""Tests for notes and quizzes API endpoints."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.api.deps import get_current_user
from app.models.profile import Profile
from app.models.subject import Subject
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.note import Note
from app.models.quiz import Quiz, QuizQuestion, QuizAttempt, QuizResponse, QuizStatus, QuizType, QuizDifficulty
from app.models.chat_session import ChatSession


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


@pytest.fixture
async def sample_document(db_session, test_user, test_subject):
    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="Sample.pdf", doc_type="pdf", status=DocumentStatus.READY)
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.fixture
async def sample_chunks(db_session, sample_document):
    chunks = [
        DocumentChunk(document_id=sample_document.id, page_start=1, page_end=1, content="Photosynthesis is the process by which plants convert light energy into chemical energy.", token_count=20),
        DocumentChunk(document_id=sample_document.id, page_start=2, page_end=2, content="The equation for photosynthesis is: 6CO2 + 6H2O → C6H12O6 + 6O2.", token_count=22),
    ]
    db_session.add_all(chunks)
    await db_session.commit()
    for c in chunks:
        await db_session.refresh(c)
    return chunks


# ===================== NOTES TESTS =====================

class TestNotesCRUD:
    @pytest.mark.asyncio
    async def test_list_notes_empty(self, db_session, test_user, client):
        response = client.get("/api/notes")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_note(self, db_session, test_user, client, test_subject):
        response = client.post("/api/notes", json={
            "subject_id": str(test_subject.id),
            "title": "My Notes",
            "note_type": "summary",
            "content": "Important concepts here.",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Notes"
        assert data["note_type"] == "summary"
        assert data["content"] == "Important concepts here."

    @pytest.mark.asyncio
    async def test_get_note(self, db_session, test_user, client):
        note = Note(owner_id=test_user.id, title="Test Note", note_type="summary", content="Content")
        db_session.add(note)
        await db_session.commit()
        await db_session.refresh(note)

        response = client.get(f"/api/notes/{note.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(note.id)

    @pytest.mark.asyncio
    async def test_update_note(self, db_session, test_user, client):
        note = Note(owner_id=test_user.id, title="Old Title", note_type="summary", content="Old content")
        db_session.add(note)
        await db_session.commit()
        await db_session.refresh(note)

        response = client.put(f"/api/notes/{note.id}", json={
            "title": "New Title",
            "content": "New content",
        })
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_delete_note(self, db_session, test_user, client):
        note = Note(owner_id=test_user.id, title="To Delete", note_type="summary", content="x")
        db_session.add(note)
        await db_session.commit()
        await db_session.refresh(note)

        response = client.delete(f"/api/notes/{note.id}")
        assert response.status_code == 204

        response = client.get(f"/api/notes/{note.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_note_ownership_isolation(self, db_session, client):
        from app.models.profile import Profile
        other_user = Profile(sub="other-sub", email="other@example.com", full_name="Other")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        note = Note(owner_id=other_user.id, title="Other's Note", note_type="summary", content="x")
        db_session.add(note)
        await db_session.commit()
        await db_session.refresh(note)

        response = client.get(f"/api/notes/{note.id}")
        assert response.status_code == 404


class TestNotesGenerate:
    @pytest.mark.asyncio
    async def test_generate_note_requires_subject_or_document(self, db_session, test_user, client):
        response = client.post("/api/notes/generate", params={
            "note_type": "summary",
            "title": "Generated Note",
        })
        assert response.status_code == 422
        assert response.json()["detail"] == "Either document_id or subject_id must be provided"

    @pytest.mark.asyncio
    async def test_generate_note_with_subject_id_passes_validation(
        self, db_session, test_user, client, test_subject, sample_document, sample_chunks
    ):
        with patch("app.services.notes.generate_notes", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "A summary of the subject."
            response = client.post("/api/notes/generate", params={
                "subject_id": str(test_subject.id),
                "note_type": "summary",
                "title": "Subject Note",
            })
        assert response.status_code == 201
        data = response.json()
        assert data["subject_id"] == str(test_subject.id)
        assert data["title"] == "Subject Note"


# ===================== QUIZZES TESTS =====================

class TestQuizzesGenerate:
    @pytest.mark.asyncio
    async def test_generate_quiz_no_chunks(self, db_session, test_user, client, test_subject):
        """Generate without any document chunks should fail."""
        response = client.post("/api/quizzes/generate", json={
            "subject_id": str(test_subject.id),
            "title": "Quiz",
            "quiz_type": "mcq",
            "difficulty": "medium",
            "question_count": 3,
        })
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_quiz_success(self, db_session, test_user, client, test_subject, sample_document, sample_chunks):
        mock_questions = [
            {
                "question_text": "What is photosynthesis?",
                "question_type": "mcq",
                "options": ["A) Process of making food", "B) Process of breathing", "C) Process of eating", "D) Process of sleeping"],
                "correct_option_index": 0,
                "explanation": "Photosynthesis converts light to chemical energy.",
            },
            {
                "question_text": "What is the photosynthesis equation?",
                "question_type": "short_answer",
                "model_answer": "6CO2 + 6H2O → C6H12O6 + 6O2",
                "explanation": "This is the balanced equation.",
            },
        ]
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": mock_questions}
            response = client.post("/api/quizzes/generate", json={
                "document_id": str(sample_document.id),
                "title": "Photosynthesis Quiz",
                "quiz_type": "mixed",
                "difficulty": "medium",
                "question_count": 2,
            })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Photosynthesis Quiz"
        assert data["quiz_type"] == "mixed"
        assert len(data["questions"]) == 2

    @pytest.mark.asyncio
    async def test_generate_quiz_requires_subject_or_document(self, db_session, test_user, client):
        response = client.post("/api/quizzes/generate", json={
            "title": "Quiz",
            "quiz_type": "mcq",
            "difficulty": "medium",
            "question_count": 3,
        })
        assert response.status_code == 422
        assert response.json()["detail"] == "Either document_id or subject_id must be provided"

    @pytest.mark.asyncio
    async def test_generate_quiz_with_subject_id_passes_validation(
        self, db_session, test_user, client, test_subject, sample_document, sample_chunks
    ):
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": [
                {
                    "question_text": "What is photosynthesis?",
                    "question_type": "mcq",
                    "options": ["A", "B", "C", "D"],
                    "correct_option_index": 0,
                    "explanation": "Photosynthesis.",
                },
            ]}
            response = client.post("/api/quizzes/generate", json={
                "subject_id": str(test_subject.id),
                "title": "Subject Quiz",
                "quiz_type": "mcq",
                "difficulty": "medium",
                "question_count": 1,
            })
        assert response.status_code == 201
        assert response.json()["subject_id"] == str(test_subject.id)


class TestQuizzesList:
    @pytest.mark.asyncio
    async def test_list_quizzes_empty(self, db_session, test_user, client):
        response = client.get("/api/quizzes")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_quizzes_ownership(self, db_session, client):
        from app.models.profile import Profile
        other = Profile(sub="other2", email="other2@example.com", full_name="Other2")
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)

        quiz = Quiz(owner_id=other.id, title="Other Quiz", quiz_type=QuizType.MCQ, difficulty=QuizDifficulty.MEDIUM, question_count=1, status=QuizStatus.DRAFT)
        db_session.add(quiz)
        await db_session.commit()

        response = client.get("/api/quizzes")
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestQuizzesSubmit:
    @pytest.mark.asyncio
    async def test_submit_mcq_quiz(self, db_session, test_user, client, sample_document, sample_chunks):
        mock_questions = [
            {
                "question_text": "What is 2+2?",
                "question_type": "mcq",
                "options": ["A) 3", "B) 4", "C) 5", "D) 6"],
                "correct_option_index": 1,
                "explanation": "Basic arithmetic.",
            },
        ]
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": mock_questions}
            gen_resp = client.post("/api/quizzes/generate", json={
                "document_id": str(sample_document.id),
                "title": "Math Quiz",
                "quiz_type": "mcq",
                "difficulty": "easy",
                "question_count": 1,
            })
        quiz_id = gen_resp.json()["id"]

        # Submit correct answer
        response = client.post(f"/api/quizzes/{quiz_id}/submit", json={
            "responses": [
                {"question_id": gen_resp.json()["questions"][0]["id"], "selected_option_index": 1}
            ]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["score"] == 100
        assert data["correct_answers"] == 1
        assert len(data["responses"]) == 1
        assert data["responses"][0]["is_correct"] is True

    @pytest.mark.asyncio
    async def test_submit_wrong_answer(self, db_session, test_user, client, sample_document, sample_chunks):
        mock_questions = [
            {
                "question_text": "What is the capital of France?",
                "question_type": "mcq",
                "options": ["A) London", "B) Berlin", "C) Paris", "D) Madrid"],
                "correct_option_index": 2,
            },
        ]
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": mock_questions}
            gen_resp = client.post("/api/quizzes/generate", json={
                "document_id": str(sample_document.id),
                "title": "Geo Quiz",
                "quiz_type": "mcq",
                "difficulty": "easy",
                "question_count": 1,
            })
        quiz_id = gen_resp.json()["id"]

        # Submit wrong answer
        response = client.post(f"/api/quizzes/{quiz_id}/submit", json={
            "responses": [
                {"question_id": gen_resp.json()["questions"][0]["id"], "selected_option_index": 0}
            ]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["score"] == 0
        assert data["responses"][0]["is_correct"] is False

    @pytest.mark.asyncio
    async def test_submit_short_answer(self, db_session, test_user, client, sample_document, sample_chunks):
        mock_questions = [
            {
                "question_text": "Explain photosynthesis.",
                "question_type": "short_answer",
                "model_answer": "Photosynthesis is the process by which plants convert light energy into chemical energy using CO2 and water to produce glucose and oxygen.",
                "explanation": "Key process in biology.",
            },
        ]
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": mock_questions}
            gen_resp = client.post("/api/quizzes/generate", json={
                "document_id": str(sample_document.id),
                "title": "Biology Quiz",
                "quiz_type": "short_answer",
                "difficulty": "medium",
                "question_count": 1,
            })
        quiz_id = gen_resp.json()["id"]

        # Submit answer with good keyword overlap
        response = client.post(f"/api/quizzes/{quiz_id}/submit", json={
            "responses": [
                {"question_id": gen_resp.json()["questions"][0]["id"], "user_answer": "Plants convert light into chemical energy using CO2 and water"}
            ]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["responses"][0]["is_correct"] is True


class TestQuizSummary:
    @pytest.mark.asyncio
    async def test_quiz_summary(self, db_session, test_user, client, sample_document, sample_chunks):
        mock_questions = [{"question_text": "Q1", "question_type": "mcq", "options": ["A) x", "B) y", "C) z", "D) w"], "correct_option_index": 1, "explanation": "exp"}]
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": mock_questions}
            gen_resp = client.post("/api/quizzes/generate", json={
                "document_id": str(sample_document.id),
                "title": "Summary Quiz",
                "quiz_type": "mcq",
                "difficulty": "easy",
                "question_count": 1,
            })
        quiz_id = gen_resp.json()["id"]

        # Submit one attempt
        qid = gen_resp.json()["questions"][0]["id"]
        client.post(f"/api/quizzes/{quiz_id}/submit", json={
            "responses": [{"question_id": qid, "selected_option_index": 1}]
        })

        # Get summary
        response = client.get(f"/api/quizzes/{quiz_id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_attempts"] == 1
        assert data["best_score"] == 100


class TestDeleteQuiz:
    @pytest.mark.asyncio
    async def test_delete_quiz(self, db_session, test_user, client, sample_document, sample_chunks):
        mock_questions = [{"question_text": "Q1", "question_type": "mcq", "options": ["A) x", "B) y", "C) z", "D) w"], "correct_option_index": 0}]
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": mock_questions}
            gen_resp = client.post("/api/quizzes/generate", json={
                "document_id": str(sample_document.id),
                "title": "Delete Me",
                "quiz_type": "mcq",
                "difficulty": "easy",
                "question_count": 1,
            })
        quiz_id = gen_resp.json()["id"]

        response = client.delete(f"/api/quizzes/{quiz_id}")
        assert response.status_code == 204

        response = client.get(f"/api/quizzes/{quiz_id}")
        assert response.status_code == 404


class TestQuizAnswerKeyLeak:
    @pytest.mark.asyncio
    async def test_answer_keys_hidden_until_submit(
        self, db_session, test_user, client, sample_document, sample_chunks
    ):
        mock_questions = [
            {
                "question_text": "What is photosynthesis?",
                "question_type": "mcq",
                "options": ["A) food", "B) sleep", "C) breathing", "D) eating"],
                "correct_option_index": 0,
                "explanation": "Secret explanation",
            },
            {
                "question_text": "State the equation.",
                "question_type": "short_answer",
                "model_answer": "6CO2 + 6H2O",
                "explanation": "Secret short explanation",
            },
        ]
        with patch("app.services.quizzes.generate_quiz") as mock_gen:
            mock_gen.return_value = {"questions": mock_questions}
            gen_resp = client.post("/api/quizzes/generate", json={
                "document_id": str(sample_document.id),
                "title": "Leak Check",
                "quiz_type": "mixed",
                "difficulty": "easy",
                "question_count": 2,
            })
        assert gen_resp.status_code == 201
        quiz_id = gen_resp.json()["id"]

        def assert_hidden(questions):
            for q in questions:
                assert q["correct_option_index"] is None
                assert q["model_answer"] is None
                assert q["explanation"] is None

        assert_hidden(gen_resp.json()["questions"])
        get_resp = client.get(f"/api/quizzes/{quiz_id}")
        assert get_resp.status_code == 200
        assert_hidden(get_resp.json()["questions"])

        questions = get_resp.json()["questions"]
        submit_resp = client.post(f"/api/quizzes/{quiz_id}/submit", json={
            "responses": [
                {"question_id": questions[0]["id"], "selected_option_index": 0},
                {"question_id": questions[1]["id"], "user_answer": "6CO2 + 6H2O"},
            ]
        })
        assert submit_resp.status_code == 201
        responses = submit_resp.json()["responses"]
        assert responses[0]["correct_option_index"] == 0
        assert responses[0]["explanation"] == "Secret explanation"
        assert responses[1]["model_answer"] == "6CO2 + 6H2O"
        assert all(r["is_correct"] is True for r in responses)
