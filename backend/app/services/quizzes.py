"""Quiz generation and grading services."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.resilience import call_with_retry
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


# --- Request/Response models ---

class MCQQuestion(BaseModel):
    question_text: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=2, max_length=4)
    correct_option_index: int = Field(..., ge=0)
    explanation: str | None = None

    @field_validator("correct_option_index")
    @classmethod
    def validate_option_index(cls, v, info):
        options = info.data.get("options", [])
        if options and not (0 <= v < len(options)):
            raise ValueError(f"correct_option_index {v} out of range for {len(options)} options")
        return v


class ShortAnswerQuestion(BaseModel):
    question_text: str = Field(..., min_length=1)
    model_answer: str = Field(..., min_length=1)
    explanation: str | None = None


class QuizGenerationRequest(BaseModel):
    quiz_type: str = Field(..., pattern="^(mcq|short_answer|mixed)$")
    difficulty: str = Field(..., pattern="^(easy|medium|hard)$")
    question_count: int = Field(..., ge=1, le=20)


@dataclass
class GradingResult:
    question_id: str
    is_correct: bool
    selected_option_index: int | None = None
    user_answer: str | None = None
    correct_option_index: int | None = None
    model_answer: str | None = None
    explanation: str | None = None


# --- Prompts ---

_MCQ_PROMPT = """\
You are a study assistant creating quiz questions from study materials.
Create {count} multiple-choice questions at {difficulty} difficulty.
Each question must have exactly 4 options (A, B, C, D).
Only one option is correct.
Base questions strictly on the provided materials — do not invent facts.

Return ONLY valid JSON matching this schema (no extra text):
{{"questions": [
  {{
    "question_text": "...",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct_option_index": 0,
    "explanation": "..."
  }}
]}}"""

_SHORT_ANSWER_PROMPT = """\
You are a study assistant creating short-answer quiz questions from study materials.
Create {count} short-answer questions at {difficulty} difficulty.
Questions should test understanding, not just memorization.
Base questions strictly on the provided materials — do not invent facts.

Return ONLY valid JSON matching this schema (no extra text):
{{"questions": [
  {{
    "question_text": "...",
    "model_answer": "The expected answer",
    "explanation": "Why this is correct"
  }}
]}}"""

_MIXED_PROMPT = """\
You are a study assistant creating quiz questions from study materials.
Create {count} questions total, roughly half multiple-choice and half short-answer,
at {difficulty} difficulty.
Base questions strictly on the provided materials — do not invent facts.

Return ONLY valid JSON matching this schema (no extra text):
{{"questions": [
  {{"type": "mcq", "question_text": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_option_index": 0, "explanation": "..."}},
  {{"type": "short_answer", "question_text": "...", "model_answer": "...", "explanation": "..."}}
]}}"""


def _build_references(chunks: list[DocumentChunk]) -> str:
    """Build reference text from document chunks."""
    refs = []
    for chunk in chunks:
        refs.append(f"[Chunk {chunk.id}]\n{chunk.content}")
    return "\n---\n".join(refs) if refs else ""


async def generate_quiz(
    chunks: list[DocumentChunk],
    quiz_type: str,
    difficulty: str,
    question_count: int,
) -> dict:
    """Generate quiz questions from document chunks using Gemini.

    Args:
        chunks: Document chunks to base quiz on
        quiz_type: 'mcq', 'short_answer', or 'mixed'
        difficulty: 'easy', 'medium', or 'hard'
        question_count: Number of questions to generate

    Returns:
        Dict with 'questions' list and metadata
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your-gemini-api-key":
        raise RuntimeError("GEMINI_API_KEY is not configured")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    if not chunks:
        raise ValueError("No document chunks available to generate quiz questions")

    references = _build_references(chunks)

    if quiz_type == "mcq":
        prompt = _MCQ_PROMPT.format(count=question_count, difficulty=difficulty)
    elif quiz_type == "short_answer":
        prompt = _SHORT_ANSWER_PROMPT.format(count=question_count, difficulty=difficulty)
    else:  # mixed
        prompt = _MIXED_PROMPT.format(count=question_count, difficulty=difficulty)

    full_prompt = f"{prompt}\n\nMATERIALS:\n{references}"

    try:
        response = await call_with_retry(
            model.generate_content,
            full_prompt,
            generation_config={"temperature": 0.3, "response_mime_type": "application/json"},
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
            retries=settings.GEMINI_MAX_RETRIES,
        )

        text = response.text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Quiz generation returned non-JSON: %s", text[:200])
            raise ValueError("Failed to parse quiz generation response")

        raw_questions = data.get("questions", [])
        questions = []

        for i, q in enumerate(raw_questions):
            qtype = q.get("type", quiz_type)
            if qtype == "mcq" or (quiz_type == "mcq"):
                try:
                    mcq = MCQQuestion(**q)
                    questions.append({
                        "question_text": mcq.question_text,
                        "question_type": "mcq",
                        "options": mcq.options,
                        "correct_option_index": mcq.correct_option_index,
                        "explanation": mcq.explanation,
                        "order": i,
                    })
                except Exception:
                    pass  # skip malformed MCQ
            elif qtype == "short_answer" or (quiz_type == "short_answer"):
                try:
                    sa = ShortAnswerQuestion(**q)
                    questions.append({
                        "question_text": sa.question_text,
                        "question_type": "short_answer",
                        "model_answer": sa.model_answer,
                        "explanation": sa.explanation,
                        "order": i,
                    })
                except Exception:
                    pass  # skip malformed short answer

        return {"questions": questions}

    except Exception as exc:
        logger.error("Quiz generation failed: %s", exc)
        raise RuntimeError(f"Quiz generation failed: {exc}")


def grade_short_answer(
    user_answer: str,
    model_answer: str,
) -> GradingResult:
    """Grade a short answer using simple keyword overlap (rule-based, no AI).

    Returns GradingResult with is_correct based on keyword overlap score >= 0.5.
    """
    user_words = set(user_answer.lower().split())
    model_words = set(model_answer.lower().split())

    if not model_words:
        return GradingResult(
            question_id="",
            is_correct=False,
            user_answer=user_answer,
            model_answer=model_answer,
        )

    overlap = len(user_words & model_words) / len(model_words)
    is_correct = overlap >= 0.5

    return GradingResult(
        question_id="",
        is_correct=is_correct,
        user_answer=user_answer,
        model_answer=model_answer,
    )


def grade_mcq(
    selected_index: int | None,
    correct_index: int,
) -> GradingResult:
    """Grade an MCQ question."""
    is_correct = selected_index == correct_index
    return GradingResult(
        question_id="",
        is_correct=is_correct,
        selected_option_index=selected_index,
        correct_option_index=correct_index,
    )
