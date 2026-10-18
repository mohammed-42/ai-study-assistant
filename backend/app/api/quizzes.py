"""Quiz API endpoints — answer keys protected in list/get responses."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.quiz import Quiz, QuizQuestion, QuizAttempt, QuizResponse, QuizStatus
from app.models.note import Note
from app.models.profile import Profile
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.quiz import (
    QuizGenerateRequest,
    QuizOut,
    QuizQuestionOut,
    QuizAttemptSubmitRequest,
    QuizResponseOut,
    QuizAttemptOut,
    QuizSummaryOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


# --- List / Create ---

@router.get("", response_model=list[dict])
async def list_quizzes(
    subject_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """List quizzes owned by current user — answer keys stripped."""
    stmt = select(Quiz).where(Quiz.owner_id == user.id)
    if subject_id:
        from app.models.subject import Subject
        subj = await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.owner_id == user.id)
        )
        if subj.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")
        stmt = stmt.where(Quiz.subject_id == subject_id)
    stmt = stmt.order_by(Quiz.created_at.desc())
    result = await db.execute(stmt)
    quizzes = result.scalars().all()

    output = []
    for q in quizzes:
        # Count questions without loading them
        qcount_result = await db.execute(
            select(QuizQuestion).where(QuizQuestion.quiz_id == q.id)
        )
        qcount = len(qcount_result.scalars().all())
        output.append({
            "id": str(q.id),
            "owner_id": str(q.owner_id),
            "subject_id": str(q.subject_id) if q.subject_id else None,
            "document_id": str(q.document_id) if q.document_id else None,
            "title": q.title,
            "quiz_type": q.quiz_type.value if hasattr(q.quiz_type, 'value') else q.quiz_type,
            "difficulty": q.difficulty.value if hasattr(q.difficulty, 'value') else q.difficulty,
            "question_count": qcount,
            "status": q.status.value if hasattr(q.status, 'value') else q.status,
            "created_at": q.created_at.isoformat(),
            "updated_at": q.updated_at.isoformat(),
        })
    return output


@router.post("/generate", response_model=QuizOut, status_code=201)
async def generate_quiz(
    body: QuizGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Generate a quiz from document chunks using Gemini."""
    from app.services.quizzes import generate_quiz as gen_quiz_svc

    # Resolve document
    if body.document_id:
        doc = await db.execute(
            select(Document).where(Document.id == body.document_id, Document.owner_id == user.id)
        )
        doc_obj = doc.scalar_one_or_none()
        if doc_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found or not owned")
        chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == body.document_id)
        )
        chunks = chunks_result.scalars().all()
    elif body.subject_id:
        from app.models.subject import Subject
        subj = await db.execute(
            select(Subject).where(Subject.id == body.subject_id, Subject.owner_id == user.id)
        )
        if subj.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")
        docs_result = await db.execute(
            select(Document).where(Document.subject_id == body.subject_id, Document.owner_id == user.id)
        )
        docs = docs_result.scalars().all()
        chunks = []
        for d in docs:
            cr = await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == d.id)
            )
            chunks.extend(cr.scalars().all())
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either document_id or subject_id must be provided",
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No document chunks found for the selected document(s)",
        )

    try:
        quiz_data = await gen_quiz_svc(
            chunks=chunks,
            quiz_type=body.quiz_type,
            difficulty=body.difficulty,
            question_count=body.question_count,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    questions_raw = quiz_data.get("questions", [])
    if not questions_raw:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No questions generated — check materials")

    # Create quiz
    quiz = Quiz(
        owner_id=user.id,
        subject_id=body.subject_id,
        document_id=body.document_id,
        title=body.title,
        quiz_type=body.quiz_type,
        difficulty=body.difficulty,
        question_count=len(questions_raw),
        status=QuizStatus.DRAFT,
    )
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)

    # Create questions (answer keys stored but not exposed in list)
    for i, qdata in enumerate(questions_raw):
        q = QuizQuestion(
            quiz_id=quiz.id,
            question_text=qdata["question_text"],
            question_type=qdata["question_type"],
            options=json.dumps(qdata.get("options", [])),
            correct_option_index=qdata.get("correct_option_index"),
            model_answer=qdata.get("model_answer"),
            explanation=qdata.get("explanation"),
            order=i,
        )
        if body.document_id:
            q.document_id = body.document_id
        db.add(q)

    await db.commit()
    await db.refresh(quiz)

    # Load questions for response (strip keys from list view, include in get)
    q_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.order)
    )
    quiz_questions = q_result.scalars().all()

    return {
        "id": str(quiz.id),
        "owner_id": str(quiz.owner_id),
        "subject_id": str(quiz.subject_id) if quiz.subject_id else None,
        "document_id": str(quiz.document_id) if quiz.document_id else None,
        "title": quiz.title,
        "quiz_type": quiz.quiz_type,
        "difficulty": quiz.difficulty,
        "question_count": len(quiz_questions),
        "status": quiz.status,
        "created_at": quiz.created_at.isoformat(),
        "updated_at": quiz.updated_at.isoformat(),
        "questions": [
            {
                "id": str(q.id),
                "quiz_id": str(q.quiz_id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "options": json.loads(q.options) if q.options else None,
                "correct_option_index": q.correct_option_index,
                "model_answer": q.model_answer,
                "document_id": str(q.document_id) if q.document_id else None,
                "page_start": q.page_start,
                "page_end": q.page_end,
                "explanation": q.explanation,
                "order": q.order,
                "created_at": q.created_at.isoformat(),
            }
            for q in quiz_questions
        ],
    }


# --- Get (with full question details including answers) ---

@router.get("/{quiz_id}", response_model=dict)
async def get_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Get a quiz with full details including answer keys (owner only)."""
    quiz = await _get_owner_quiz(db, uuid.UUID(quiz_id), user.id)
    q_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.order)
    )
    questions = q_result.scalars().all()

    return {
        "id": str(quiz.id),
        "owner_id": str(quiz.owner_id),
        "subject_id": str(quiz.subject_id) if quiz.subject_id else None,
        "document_id": str(quiz.document_id) if quiz.document_id else None,
        "title": quiz.title,
        "quiz_type": quiz.quiz_type,
        "difficulty": quiz.difficulty,
        "question_count": len(questions),
        "status": quiz.status,
        "created_at": quiz.created_at.isoformat(),
        "updated_at": quiz.updated_at.isoformat(),
        "questions": [
            {
                "id": str(q.id),
                "quiz_id": str(q.quiz_id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "options": json.loads(q.options) if q.options else None,
                "correct_option_index": q.correct_option_index,
                "model_answer": q.model_answer,
                "document_id": str(q.document_id) if q.document_id else None,
                "page_start": q.page_start,
                "page_end": q.page_end,
                "explanation": q.explanation,
                "order": q.order,
                "created_at": q.created_at.isoformat(),
            }
            for q in questions
        ],
    }


# --- Delete ---

@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Delete a quiz and all its questions and attempts."""
    quiz = await _get_owner_quiz(db, uuid.UUID(quiz_id), user.id)
    await db.delete(quiz)
    await db.commit()
    return None


# --- Take quiz: submit answers ---

@router.post("/{quiz_id}/submit", response_model=QuizAttemptOut, status_code=201)
async def submit_quiz(
    quiz_id: str,
    body: QuizAttemptSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Submit quiz answers and get graded results."""
    quiz = await _get_owner_quiz(db, uuid.UUID(quiz_id), user.id)

    q_result = await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.order)
    )
    questions = {str(q.id): q for q in q_result.scalars().all()}

    if not questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz has no questions")

    # Create attempt
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user.id,
        total_questions=len(questions),
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    correct_count = 0
    responses_out = []

    for resp_data in body.responses:
        qid_str = resp_data.get("question_id")
        if qid_str not in questions:
            continue
        q = questions[qid_str]

        is_correct = False
        selected = None
        user_ans = None

        if q.question_type == "mcq":
            selected = resp_data.get("selected_option_index")
            from app.services.quizzes import grade_mcq
            grade = grade_mcq(selected, q.correct_option_index or -1)
            is_correct = grade.is_correct
        else:
            user_ans = resp_data.get("user_answer", "")
            from app.services.quizzes import grade_short_answer
            grade = grade_short_answer(user_ans or "", q.model_answer or "")
            is_correct = grade.is_correct

        if is_correct:
            correct_count += 1

        # Store response
        quiz_resp = QuizResponse(
            attempt_id=attempt.id,
            question_id=q.id,
            selected_option_index=selected,
            user_answer=user_ans,
            is_correct=is_correct,
        )
        db.add(quiz_resp)
        await db.flush()

        responses_out.append(QuizResponseOut(
            question_id=q.id,
            selected_option_index=selected,
            user_answer=user_ans,
            is_correct=is_correct,
            correct_option_index=q.correct_option_index,
            model_answer=q.model_answer,
            explanation=q.explanation,
        ))

    score = int(round(correct_count / len(questions) * 100)) if questions else 0
    attempt.score = score
    attempt.correct_answers = correct_count
    attempt.completed_at = attempt.completed_at or attempt.created_at
    await db.commit()
    await db.refresh(attempt)

    return QuizAttemptOut(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        user_id=attempt.user_id,
        score=attempt.score,
        total_questions=attempt.total_questions,
        correct_answers=attempt.correct_answers,
        completed_at=attempt.completed_at,
        created_at=attempt.created_at,
        responses=responses_out,
    )


# --- Attempts / Results ---

@router.get("/{quiz_id}/attempts", response_model=list[QuizAttemptOut])
async def list_attempts(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """List all quiz attempts for a quiz (owner only)."""
    await _get_owner_quiz(db, uuid.UUID(quiz_id), user.id)

    stmt = (
        select(QuizAttempt)
        .where(QuizAttempt.quiz_id == uuid.UUID(quiz_id))
        .order_by(QuizAttempt.created_at.desc())
    )
    result = await db.execute(stmt)
    attempts = result.scalars().all()

    output = []
    for attempt in attempts:
        resp_stmt = (
            select(QuizResponse)
            .where(QuizResponse.attempt_id == attempt.id)
            .order_by(QuizResponse.created_at.asc())
        )
        resp_result = await db.execute(resp_stmt)
        responses = resp_result.scalars().all()

        # Load question details for each response
        q_ids = [r.question_id for r in responses]
        q_stmt = select(QuizQuestion).where(QuizQuestion.id.in_(q_ids))
        q_result = await db.execute(q_stmt)
        questions_map = {str(q.id): q for q in q_result.scalars().all()}

        resp_out = []
        for r in responses:
            q = questions_map.get(str(r.question_id))
            resp_out.append(QuizResponseOut(
                question_id=r.question_id,
                selected_option_index=r.selected_option_index,
                user_answer=r.user_answer,
                is_correct=r.is_correct,
                correct_option_index=q.correct_option_index if q else None,
                model_answer=q.model_answer if q else None,
                explanation=q.explanation if q else None,
            ))

        output.append(QuizAttemptOut(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            user_id=attempt.user_id,
            score=attempt.score,
            total_questions=attempt.total_questions,
            correct_answers=attempt.correct_answers,
            completed_at=attempt.completed_at,
            created_at=attempt.created_at,
            responses=resp_out,
        ))
    return output


@router.get("/{quiz_id}/summary", response_model=QuizSummaryOut)
async def get_quiz_summary(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Get quiz performance summary."""
    await _get_owner_quiz(db, uuid.UUID(quiz_id), user.id)

    stmt = (
        select(QuizAttempt)
        .where(
            QuizAttempt.quiz_id == uuid.UUID(quiz_id),
            QuizAttempt.user_id == user.id,
        )
        .order_by(QuizAttempt.created_at.desc())
    )
    result = await db.execute(stmt)
    attempts = result.scalars().all()

    scores = [a.score for a in attempts if a.score is not None]
    avg_score = sum(scores) / len(scores) if scores else None
    best_score = max(scores) if scores else None

    # Limit recent attempts to 5
    recent = []
    for attempt in attempts[:5]:
        resp_stmt = (
            select(QuizResponse)
            .where(QuizResponse.attempt_id == attempt.id)
            .order_by(QuizResponse.created_at.asc())
        )
        resp_result = await db.execute(resp_stmt)
        responses = resp_result.scalars().all()

        q_ids = [r.question_id for r in responses]
        q_stmt = select(QuizQuestion).where(QuizQuestion.id.in_(q_ids))
        q_result = await db.execute(q_stmt)
        questions_map = {str(q.id): q for q in q_result.scalars().all()}

        resp_out = []
        for r in responses:
            q = questions_map.get(str(r.question_id))
            resp_out.append(QuizResponseOut(
                question_id=r.question_id,
                selected_option_index=r.selected_option_index,
                user_answer=r.user_answer,
                is_correct=r.is_correct,
                correct_option_index=q.correct_option_index if q else None,
                model_answer=q.model_answer if q else None,
                explanation=q.explanation if q else None,
            ))

        recent.append(QuizAttemptOut(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            user_id=attempt.user_id,
            score=attempt.score,
            total_questions=attempt.total_questions,
            correct_answers=attempt.correct_answers,
            completed_at=attempt.completed_at,
            created_at=attempt.created_at,
            responses=resp_out,
        ))

    return QuizSummaryOut(
        total_attempts=len(attempts),
        average_score=round(avg_score, 1) if avg_score is not None else None,
        best_score=best_score,
        recent_attempts=recent,
    )


async def _get_owner_quiz(db: AsyncSession, quiz_id: uuid.UUID, owner_id: uuid.UUID) -> Quiz:
    stmt = select(Quiz).where(Quiz.id == quiz_id, Quiz.owner_id == owner_id)
    result = await db.execute(stmt)
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quiz not found or not owned")
    return quiz
