from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QuizGenerateRequest(BaseModel):
    subject_id: UUID | None = None
    document_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    quiz_type: str = Field(default="mixed", pattern="^(mcq|short_answer|mixed)$")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    question_count: int = Field(default=5, ge=1, le=20)

    @field_validator("quiz_type")
    @classmethod
    def validate_quiz_type(cls, v):
        if v == "mixed":
            pass
        return v


class QuizQuestionOut(BaseModel):
    id: UUID
    quiz_id: UUID
    question_text: str
    question_type: str
    options: list[str] | None = None
    correct_option_index: int | None = None
    model_answer: str | None = None
    document_id: UUID | None
    page_start: int | None
    page_end: int | None
    explanation: str | None
    order: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        data = {
            "id": obj.id,
            "quiz_id": obj.quiz_id,
            "question_text": obj.question_text,
            "question_type": obj.question_type,
            "document_id": obj.document_id,
            "page_start": obj.page_start,
            "page_end": obj.page_end,
            "explanation": obj.explanation,
            "order": obj.order,
            "created_at": obj.created_at,
        }
        if obj.options:
            try:
                data["options"] = json.loads(obj.options)
            except (json.JSONDecodeError, TypeError):
                data["options"] = None
        else:
            data["options"] = None
        data["correct_option_index"] = obj.correct_option_index
        data["model_answer"] = obj.model_answer
        return cls(**data)


class QuizOut(BaseModel):
    id: UUID
    owner_id: UUID
    subject_id: UUID | None
    document_id: UUID | None
    title: str
    quiz_type: str
    difficulty: str
    question_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    questions: list[QuizQuestionOut] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        data = {
            "id": obj.id,
            "owner_id": obj.owner_id,
            "subject_id": obj.subject_id,
            "document_id": obj.document_id,
            "title": obj.title,
            "quiz_type": obj.quiz_type,
            "difficulty": obj.difficulty,
            "question_count": obj.question_count,
            "status": obj.status,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        if hasattr(obj, "questions"):
            data["questions"] = [QuizQuestionOut.from_orm(q) for q in obj.questions]
        return cls(**data)


class QuizAttemptSubmitRequest(BaseModel):
    responses: list[dict] = Field(..., min_length=1)
    # Each response: {"question_id": str, "selected_option_index": int|None, "user_answer": str|None}


class QuizResponseOut(BaseModel):
    question_id: UUID
    selected_option_index: int | None
    user_answer: str | None
    is_correct: bool
    correct_option_index: int | None = None
    model_answer: str | None = None
    explanation: str | None = None


class QuizAttemptOut(BaseModel):
    id: UUID
    quiz_id: UUID
    user_id: UUID
    score: int | None
    total_questions: int
    correct_answers: int
    completed_at: datetime | None
    created_at: datetime
    responses: list[QuizResponseOut] = []

    model_config = {"from_attributes": True}


class QuizSummaryOut(BaseModel):
    total_attempts: int
    average_score: float | None
    best_score: int | None
    recent_attempts: list[QuizAttemptOut]
