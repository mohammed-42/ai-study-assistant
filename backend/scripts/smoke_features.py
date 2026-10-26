"""Live feature smoke test: tutor, notes, quizzes, planner (single script).

Creates one SMOKE TEST subject and deletes only what it creates. Any HTTP 429
or Gemini quota response stops the run; cleanup still executes in ``finally``.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env.smoke")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", "documents")
DATABASE_URL_SYNC = os.environ["DATABASE_URL_SYNC"]
SMOKE_EMAIL = os.environ["SMOKE_EMAIL"]
SMOKE_PASSWORD = os.environ["SMOKE_PASSWORD"]
SMOKE_PDF = os.environ["SMOKE_PDF"]

API_BASE = "http://localhost:8000/api"
HTTP_TIMEOUT = 180.0
PROCESS_TIMEOUT = 300.0
SUBJECT_PREFIX = "SMOKE TEST"


class StepFailed(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step
        self.message = message


class QuotaExceeded(Exception):
    pass


def first_line(exc: BaseException | str) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else exc.__class__.__name__


def passed(step: str, proof: str) -> None:
    print(f"PASSED: {step} | proof: {proof}", flush=True)


def failed(step: str, exc: BaseException | str) -> None:
    print(f"FAILED: {step} | error: {first_line(exc)}", flush=True)


def db_connect():
    last_error = None
    for attempt in range(5):
        try:
            return psycopg2.connect(DATABASE_URL_SYNC, connect_timeout=20)
        except Exception as exc:
            last_error = exc
            print(f"DB_CONNECT_RETRY {attempt + 1}/5: {first_line(exc)}", flush=True)
            time.sleep(5)
    raise last_error  # type: ignore[misc]


def scalar(cur, sql: str, params=()):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def request(api: httpx.Client, step: str, method: str, path: str, **kwargs):
    try:
        response = api.request(method, path, timeout=HTTP_TIMEOUT, **kwargs)
    except httpx.HTTPError as exc:
        raise StepFailed(step, first_line(exc)) from exc
    body = response.text
    if response.status_code == 429 or "ResourceExhausted" in body:
        raise QuotaExceeded(f"{step}: HTTP {response.status_code} {body[:200]}")
    if response.status_code >= 500 and (
        "usage limit" in body.lower() or "quota" in body.lower()
    ):
        raise QuotaExceeded(f"{step}: HTTP {response.status_code} {body[:200]}")
    return response


def expect(step: str, response, statuses: tuple[int, ...]):
    if response.status_code not in statuses:
        raise StepFailed(
            step, f"HTTP {response.status_code}: {response.text[:300]}"
        )
    return response


def storage_client():
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def list_storage_names(folder: str) -> list[str]:
    client = storage_client()
    items = client.storage.from_(STORAGE_BUCKET).list(folder)
    return [item.get("name") for item in items if item.get("name")]


def count_ids(cur, table: str, column: str, ids: list[str]) -> int:
    if not ids:
        return 0
    placeholders = ",".join(["%s"] * len(ids))
    cur.execute(
        f"select count(*) from {table} where {column} in ({placeholders})",
        tuple(ids),
    )
    return cur.fetchone()[0]


def paraphrase(model_answer: str) -> str:
    words = [w.lower() for w in model_answer.split() if w.strip()]
    unique = list(dict.fromkeys(words))
    if len(unique) <= 1:
        return model_answer
    keep = max(1, int(len(unique) * 0.75))
    return " ".join(unique[:keep])


def login() -> str:
    response = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
        timeout=HTTP_TIMEOUT,
    )
    if response.status_code != 200:
        raise StepFailed(
            "login", f"HTTP {response.status_code}: {response.text[:300]}"
        )
    token = response.json().get("access_token")
    if not token:
        raise StepFailed("login", "login response did not contain access_token")
    return token


def task0_cleanup(api, cur, state) -> None:
    cur.execute(
        "select id, name from subjects where name like %s order by created_at",
        (SUBJECT_PREFIX + "%",),
    )
    subjects = cur.fetchall()
    removed_subjects = 0
    removed_documents = 0
    for subject_id, subject_name in subjects:
        cur.execute(
            "select id, name, storage_key from documents where subject_id=%s",
            (subject_id,),
        )
        docs = cur.fetchall()
        print(
            f"TASK0_LEFTOVER subject={subject_id} name={subject_name} "
            f"documents={len(docs)}",
            flush=True,
        )
        for doc_id, doc_name, storage_key in docs:
            print(
                f"TASK0_LEFTOVER_DOC subject={subject_id} document={doc_id} "
                f"name={doc_name} storage_key_set={bool(storage_key)}",
                flush=True,
            )
            response = request(
                api, "task0 delete leftover document", "DELETE", f"/documents/{doc_id}"
            )
            if response.status_code not in (200, 204, 404):
                raise StepFailed(
                    "task0 delete leftover document",
                    f"HTTP {response.status_code}: {response.text[:200]}",
                )
            removed_documents += 1
        response = request(
            api, "task0 delete leftover subject", "DELETE", f"/subjects/{subject_id}"
        )
        if response.status_code not in (200, 204, 404):
            raise StepFailed(
                "task0 delete leftover subject",
                f"HTTP {response.status_code}: {response.text[:200]}",
            )
        removed_subjects += 1

    remaining = scalar(
        cur,
        "select count(*) from subjects where name like %s",
        (SUBJECT_PREFIX + "%",),
    )
    print(
        f"TASK0_REMOVED subjects={removed_subjects} documents={removed_documents} "
        f"remaining={remaining}",
        flush=True,
    )
    if remaining:
        raise StepFailed("task0", f"{remaining} SMOKE TEST subject(s) remain")
    passed(
        "TASK 0 leftover cleanup",
        f"removed_subjects={removed_subjects} removed_documents={removed_documents} "
        f"remaining=0",
    )


def task1_setup(api, cur, state) -> None:
    name = f"{SUBJECT_PREFIX} {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    response = expect(
        "create subject",
        request(api, "create subject", "POST", "/subjects/", json={"name": name}),
        (201,),
    )
    subject = response.json()
    state["subject_id"] = subject["id"]
    passed("create subject", f"id={subject['id']} name={name}")

    pdf_path = Path(SMOKE_PDF)
    if not pdf_path.is_absolute():
        pdf_path = (BACKEND_DIR / pdf_path).resolve()
    if not pdf_path.exists():
        raise StepFailed("upload PDF", f"SMOKE_PDF not found: {pdf_path}")
    response = expect(
        "upload PDF",
        request(
            api,
            "upload PDF",
            "POST",
            "/documents/upload",
            params={"subject_id": subject["id"], "doc_type": "pdf"},
            files={"files": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
        ),
        (201,),
    )
    document = response.json()
    state["doc_id"] = document["id"]
    state["owner_id"] = document["owner_id"]
    state["doc_name"] = document["name"]
    print(
        f"TASK1_UPLOAD id={document['id']} status={document.get('status')} "
        f"name={document['name']}",
        flush=True,
    )

    poll_start = time.time()
    deadline = poll_start + PROCESS_TIMEOUT
    status = None
    page_count = 0
    error_message = None
    while time.time() < deadline:
        response = expect(
            "poll document",
            request(api, "poll document", "GET", f"/documents/{document['id']}"),
            (200,),
        )
        payload = response.json()
        status = payload.get("status")
        page_count = payload.get("page_count", 0)
        error_message = payload.get("error_message")
        if status in ("ready", "failed"):
            break
        time.sleep(3)
    elapsed = time.time() - poll_start
    if status != "ready":
        raise StepFailed(
            "poll document",
            f"status={status} seconds={elapsed:.1f} error={first_line(error_message or 'none')}",
        )
    passed(
        "upload PDF and wait ready",
        f"status={status} page_count={page_count} seconds={elapsed:.1f}",
    )

    response = expect(
        "load chunks",
        request(api, "load chunks", "GET", f"/documents/{document['id']}/chunks"),
        (200,),
    )
    chunks = response.json()
    if not chunks:
        raise StepFailed("load chunks", "document has no chunks")
    state["chunks"] = {str(c["id"]): c for c in chunks}
    passed(
        "load chunks",
        f"chunk_count={len(chunks)} min_page={min(c['page_start'] for c in chunks)}",
    )


def task2_tutor(api, state) -> None:
    response = expect(
        "create chat session",
        request(
            api,
            "create chat session",
            "POST",
            "/chat/sessions",
            json={
                "subject_id": state["subject_id"],
                "title": f"{SUBJECT_PREFIX} tutor",
            },
        ),
        (201,),
    )
    session_id = response.json()["id"]
    state["session_id"] = session_id
    passed("create chat session", f"id={session_id}")

    def ask(step: str, question: str):
        response = expect(
            step,
            request(
                api,
                step,
                "POST",
                f"/chat/sessions/{session_id}/messages",
                json={"content": question, "subject_id": state["subject_id"]},
            ),
            (201,),
        )
        return response.json()

    first = ask("tutor question", "What is a component?")
    answer = first.get("content") or ""
    citations = first.get("citation_ids") or []
    chunk_map = state["chunks"]
    missing = [cid for cid in citations if str(cid) not in chunk_map]
    if not answer.strip():
        raise StepFailed("tutor question", "empty answer")
    if missing:
        raise StepFailed("tutor question", f"unknown citation ids: {missing}")
    citation_desc = [
        f"{state['doc_name']} p{chunk_map[str(cid)]['page_start']}"
        for cid in citations
    ]
    print(
        f"TUTOR_ANSWER length={len(answer)} citations={len(citations)} "
        f"citation_refs={citation_desc}",
        flush=True,
    )
    if not citations:
        raise StepFailed("tutor question", "answer had no citations")
    passed(
        "tutor grounded answer",
        f"answer_length={len(answer)} citations={len(citations)} refs={citation_desc}",
    )

    insufficient = ask(
        "tutor insufficient question", "Who won the 2018 FIFA World Cup?"
    )
    insufficient_answer = insufficient.get("content") or ""
    insufficient_citations = insufficient.get("citation_ids") or []
    if not insufficient.get("is_insufficient"):
        raise StepFailed(
            "tutor insufficient question",
            f"is_insufficient=False answer={insufficient_answer[:80]!r}",
        )
    missing2 = [
        cid for cid in insufficient_citations if str(cid) not in chunk_map
    ]
    if missing2:
        raise StepFailed(
            "tutor insufficient question", f"unknown citation ids: {missing2}"
        )
    if not insufficient_answer.strip():
        raise StepFailed("tutor insufficient question", "empty answer")
    print(
        f"TUTOR_INSUFFICIENT is_insufficient=True answer_length={len(insufficient_answer)} "
        f"citations={len(insufficient_citations)} unknown_citations=0",
        flush=True,
    )
    passed(
        "tutor insufficient evidence",
        f"is_insufficient=True answer_length={len(insufficient_answer)} "
        f"citations={len(insufficient_citations)} unknown_citations=0",
    )

    lower = answer.lower()
    if "function" in lower or "javascript" in lower:
        follow_up = "Can you give a simple example of a component like that?"
    elif "props" in lower:
        follow_up = "How do props relate to what you just described?"
    else:
        follow_up = "Can you give a simple example of that?"
    follow = ask("tutor follow-up", follow_up)
    follow_answer = follow.get("content") or ""
    if not follow_answer.strip():
        raise StepFailed("tutor follow-up", "empty answer")
    passed(
        "tutor follow-up",
        f"question={follow_up!r} answer_length={len(follow_answer)} "
        f"citations={len(follow.get('citation_ids') or [])}",
    )


def task3_notes(api, state) -> None:
    note_ids: list[str] = []
    for note_type in ("summary", "key_concepts", "definitions", "revision"):
        step = f"notes {note_type}"
        response = expect(
            step,
            request(
                api,
                step,
                "POST",
                "/notes/generate",
                params={
                    "document_id": state["doc_id"],
                    "note_type": note_type,
                    "title": f"{SUBJECT_PREFIX} {note_type}",
                },
            ),
            (201,),
        )
        note = response.json()
        note_id = note["id"]
        note_ids.append(note_id)
        content = note.get("content") or ""
        if not content.strip():
            raise StepFailed(step, "generated content is empty")
        if _is_raw_json(content):
            raise StepFailed(step, "content is a raw JSON envelope")
        fetched = expect(
            step + " retrieve",
            request(api, step + " retrieve", "GET", f"/notes/{note_id}"),
            (200,),
        ).json()
        if not (fetched.get("content") or "").strip():
            raise StepFailed(step, "saved note content is empty")
        passed(
            step,
            f"http=201 content_length={len(content)} saved=True raw_json=False",
        )
    state["note_ids"] = note_ids

    response = expect(
        "edit note",
        request(
            api,
            "edit note",
            "PUT",
            f"/notes/{note_ids[0]}",
            json={"title": f"{SUBJECT_PREFIX} edited", "content": "Edited content"},
        ),
        (200,),
    )
    edited = response.json()
    if edited.get("title") != f"{SUBJECT_PREFIX} edited" or edited.get("content") != (
        "Edited content"
    ):
        raise StepFailed("edit note", "edit was not persisted")
    passed("edit note", "title/content updated")

    response = request(api, "delete note", "DELETE", f"/notes/{note_ids[0]}")
    if response.status_code not in (200, 204):
        raise StepFailed(
            "delete note", f"HTTP {response.status_code}: {response.text[:200]}"
        )
    response = request(
        api, "delete note check", "GET", f"/notes/{note_ids[0]}"
    )
    if response.status_code != 404:
        raise StepFailed(
            "delete note check", f"HTTP {response.status_code} (expected 404)"
        )
    passed("delete note", "HTTP 204; subsequent GET 404")


def _quiz_questions(cur, quiz_id: str) -> list[dict]:
    cur.execute(
        'select id, question_text, question_type, options, '
        'correct_option_index, model_answer, explanation '
        'from quiz_questions where quiz_id=%s order by "order"',
        (quiz_id,),
    )
    rows = []
    for qid, text, qtype, options, correct, model, explanation in cur.fetchall():
        rows.append(
            {
                "id": str(qid),
                "question_text": text,
                "question_type": qtype,
                "options": json.loads(options) if options else [],
                "correct_option_index": correct,
                "model_answer": model,
                "explanation": explanation,
            }
        )
    return rows


def _submit_attempt(api, quiz_id: str, responses: list[dict]) -> dict:
    response = expect(
        "submit quiz",
        request(
            api,
            "submit quiz",
            "POST",
            f"/quizzes/{quiz_id}/submit",
            json={"responses": responses},
        ),
        (201,),
    )
    return response.json()


def _responses(questions: list[dict], *, correct: bool) -> list[dict]:
    out = []
    for q in questions:
        if q["question_type"] == "mcq":
            options = q["options"] or []
            if correct:
                index = q["correct_option_index"]
                if index is None:
                    raise StepFailed("quiz answers", "MCQ has no correct index")
            else:
                index = ((q["correct_option_index"] or 0) + 1) % max(1, len(options))
            out.append({"question_id": q["id"], "selected_option_index": index})
        else:
            model = q["model_answer"] or ""
            answer = paraphrase(model) if correct else "zzz unrelated nonsense"
            out.append({"question_id": q["id"], "user_answer": answer})
    return out


def _is_raw_json(text: str) -> bool:
    """True when the note body is an unparsed JSON envelope, not prose/code."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            stripped = "\n".join(lines[1:-1]).strip()
    if not stripped.startswith("{"):
        return False
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict)


def _check_leak(step: str, quiz: dict) -> None:
    leaks = []
    for q in quiz.get("questions", []):
        if q.get("correct_option_index") is not None:
            leaks.append(f"{q.get('id')}:correct_option_index")
        if q.get("model_answer"):
            leaks.append(f"{q.get('id')}:model_answer")
        if q.get("explanation"):
            leaks.append(f"{q.get('id')}:explanation")
    if leaks:
        raise StepFailed(step, f"answer-key leak before submit: {leaks}")


def task4_quizzes(api, cur, state) -> None:
    response = expect(
        "generate mixed quiz",
        request(
            api,
            "generate mixed quiz",
            "POST",
            "/quizzes/generate",
            json={
                "document_id": state["doc_id"],
                "title": f"{SUBJECT_PREFIX} mixed quiz",
                "quiz_type": "mixed",
                "difficulty": "medium",
                "question_count": 3,
            },
        ),
        (201,),
    )
    generated = response.json()
    quiz_id = generated["id"]
    state.setdefault("quiz_ids", []).append(quiz_id)
    if len(generated.get("questions", [])) != 3:
        raise StepFailed(
            "generate mixed quiz",
            f"expected 3 questions, got {len(generated.get('questions', []))}",
        )

    _check_leak("quiz generate leak check", generated)
    listing = expect(
        "quiz listing leak check",
        request(api, "quiz listing leak check", "GET", "/quizzes"),
        (200,),
    ).json()
    listed = next((q for q in listing if q.get("id") == quiz_id), None)
    if listed is None:
        raise StepFailed("quiz listing leak check", "generated quiz missing from list")
    _check_leak("quiz listing leak check", listed)
    fetched = expect(
        "quiz get leak check",
        request(api, "quiz get leak check", "GET", f"/quizzes/{quiz_id}"),
        (200,),
    ).json()
    _check_leak("quiz get leak check", fetched)
    passed(
        "quiz answer-key leak check",
        f"quiz_id={quiz_id} generate/list/get all hide correct_option_index, "
        f"model_answer and explanation",
    )

    questions = _quiz_questions(cur, quiz_id)
    if len(questions) != 3:
        raise StepFailed("quiz answers", f"DB has {len(questions)} questions")

    correct_attempt = _submit_attempt(
        api, quiz_id, _responses(questions, correct=True)
    )
    wrong_attempt = _submit_attempt(
        api, quiz_id, _responses(questions, correct=False)
    )
    correct_results = {
        str(r["question_id"]): r for r in correct_attempt["responses"]
    }
    wrong_results = {str(r["question_id"]): r for r in wrong_attempt["responses"]}
    print(
        f"QUIZ_ATTEMPTS correct_score={correct_attempt['score']} "
        f"wrong_score={wrong_attempt['score']}",
        flush=True,
    )
    if correct_attempt["score"] != 100 or not all(
        r["is_correct"] for r in correct_attempt["responses"]
    ):
        raise StepFailed(
            "quiz all-correct attempt",
            f"score={correct_attempt['score']} results={correct_attempt['responses']}",
        )
    if wrong_attempt["score"] != 0 or any(
        r["is_correct"] for r in wrong_attempt["responses"]
    ):
        raise StepFailed(
            "quiz all-wrong attempt",
            f"score={wrong_attempt['score']} results={wrong_attempt['responses']}",
        )
    passed(
        "quiz attempts",
        f"all_correct_score={correct_attempt['score']} "
        f"all_wrong_score={wrong_attempt['score']}",
    )

    summary = expect(
        "quiz summary",
        request(api, "quiz summary", "GET", f"/quizzes/{quiz_id}/summary"),
        (200,),
    ).json()
    if (
        summary.get("total_attempts") != 2
        or summary.get("best_score") != 100
        or summary.get("average_score") != 50.0
    ):
        raise StepFailed(
            "quiz summary",
            f"total={summary.get('total_attempts')} "
            f"avg={summary.get('average_score')} best={summary.get('best_score')}",
        )
    passed(
        "quiz summary",
        f"attempts={summary['total_attempts']} avg={summary['average_score']} "
        f"best={summary['best_score']}",
    )

    short_questions = [q for q in questions if q["question_type"] == "short_answer"]
    if not short_questions:
        response = expect(
            "generate short-answer quiz",
            request(
                api,
                "generate short-answer quiz",
                "POST",
                "/quizzes/generate",
                json={
                    "document_id": state["doc_id"],
                    "title": f"{SUBJECT_PREFIX} short answer quiz",
                    "quiz_type": "short_answer",
                    "difficulty": "medium",
                    "question_count": 1,
                },
            ),
            (201,),
        )
        short_quiz = response.json()
        short_quiz_id = short_quiz["id"]
        state["quiz_ids"].append(short_quiz_id)
        short_questions = _quiz_questions(cur, short_quiz_id)
        if not short_questions:
            raise StepFailed("generate short-answer quiz", "no questions")
        correct_sa = _submit_attempt(
            api, short_quiz_id, _responses(short_questions, correct=True)
        )
        wrong_sa = _submit_attempt(
            api, short_quiz_id, _responses(short_questions, correct=False)
        )
        correct_result = correct_sa["responses"][0]
        wrong_result = wrong_sa["responses"][0]
        correct_score = correct_sa["score"]
        wrong_score = wrong_sa["score"]
        quiz_for_sa = short_quiz_id
    else:
        sa = short_questions[0]
        correct_result = correct_results[sa["id"]]
        wrong_result = wrong_results[sa["id"]]
        correct_score = correct_attempt["score"]
        wrong_score = wrong_attempt["score"]
        quiz_for_sa = quiz_id

    if not correct_result["is_correct"]:
        raise StepFailed(
            "short-answer paraphrase",
            f"paraphrase graded wrong for question {correct_result['question_id']}",
        )
    if wrong_result["is_correct"]:
        raise StepFailed(
            "short-answer wrong answer",
            f"wrong answer graded correct for question {wrong_result['question_id']}",
        )
    passed(
        "short-answer grading",
        f"quiz={quiz_for_sa} paraphrase_is_correct=True "
        f"paraphrase_score={correct_score} wrong_is_correct=False "
        f"wrong_score={wrong_score}",
    )


def task5_planner(api, cur, state) -> None:
    today = date.today()
    exam = today + timedelta(days=14)
    topics = ["Components and JSX", "Props", "useState"]
    response = expect(
        "create plan",
        request(
            api,
            "create plan",
            "POST",
            "/planner/plans",
            json={
                "subject_id": state["subject_id"],
                "title": f"{SUBJECT_PREFIX} plan",
                "exam_date": exam.isoformat(),
                "daily_minutes": 60,
                "preferred_days": [
                    "mon",
                    "tue",
                    "wed",
                    "thu",
                    "fri",
                    "sat",
                    "sun",
                ],
                "topics": topics,
            },
        ),
        (201,),
    )
    plan = response.json()
    plan_id = plan["id"]
    state["plan_id"] = plan_id
    passed("create plan", f"id={plan_id} exam={exam.isoformat()} topics={len(topics)}")

    tasks = expect(
        "generate schedule",
        request(
            api,
            "generate schedule",
            "POST",
            f"/planner/plans/{plan_id}/generate",
        ),
        (200,),
    ).json()
    if not tasks:
        raise StepFailed("generate schedule", "no tasks generated")
    by_day: dict[str, int] = {}
    for task in tasks:
        scheduled = task.get("scheduled_date")
        if not scheduled:
            raise StepFailed("generate schedule", f"task {task['id']} has no date")
        day = date.fromisoformat(scheduled)
        if day < today:
            raise StepFailed("generate schedule", f"task scheduled before today: {day}")
        if day > exam:
            raise StepFailed("generate schedule", f"task scheduled after exam: {day}")
        by_day[scheduled] = by_day.get(scheduled, 0) + task["estimated_minutes"]
    max_day = max(by_day.values())
    if max_day > 60:
        raise StepFailed(
            "generate schedule", f"daily minutes {max_day} exceeds 60: {by_day}"
        )
    print(
        f"PLANNER_SCHEDULE tasks={len(tasks)} days={len(by_day)} "
        f"max_day_minutes={max_day} first={min(by_day)} last={max(by_day)}",
        flush=True,
    )
    passed(
        "generate schedule",
        f"tasks={len(tasks)} days={len(by_day)} max_day_minutes={max_day} "
        f"dates_within={min(by_day)}..{max(by_day)} exam={exam.isoformat()}",
    )

    done_task = tasks[0]
    response = expect(
        "mark task done",
        request(
            api,
            "mark task done",
            "PUT",
            f"/planner/tasks/{done_task['id']}",
            json={"status": "completed"},
        ),
        (200,),
    )
    if response.json().get("status") != "completed":
        raise StepFailed("mark task done", "task status was not updated")
    passed("mark task done", f"task={done_task['id']} status=completed")

    regenerated = expect(
        "regenerate schedule",
        request(
            api,
            "regenerate schedule",
            "POST",
            f"/planner/plans/{plan_id}/regenerate",
        ),
        (200,),
    ).json()
    preserved = [
        t
        for t in regenerated
        if t["id"] == done_task["id"] and t["status"] == "completed"
    ]
    if not preserved:
        raise StepFailed(
            "regenerate schedule", "completed task was not preserved"
        )
    pending_topics = [
        t["topic"] for t in regenerated if t["status"] != "completed"
    ]
    duplicate_topics = {
        topic: pending_topics.count(topic)
        for topic in set(pending_topics)
        if pending_topics.count(topic) > 1
    }
    if duplicate_topics:
        raise StepFailed(
            "regenerate schedule",
            f"duplicate pending topics: {duplicate_topics}",
        )
    print(
        f"PLANNER_REGENERATE tasks={len(regenerated)} "
        f"completed_preserved=True duplicate_pending_topics={duplicate_topics}",
        flush=True,
    )
    passed(
        "regenerate schedule",
        f"tasks={len(regenerated)} completed_preserved=True "
        f"duplicate_pending_topics={duplicate_topics}",
    )

    dashboard = expect(
        "dashboard",
        request(api, "dashboard", "GET", "/planner/dashboard"),
        (200,),
    ).json()
    owner_id = state["owner_id"]
    expected_active = scalar(
        cur,
        "select count(*) from study_plans where owner_id=%s and status='active'",
        (owner_id,),
    )
    expected_today = scalar(
        cur,
        "select count(*) from study_tasks t join study_plans p on p.id=t.plan_id "
        "where p.owner_id=%s and t.scheduled_date=%s and t.status='pending'",
        (owner_id, today),
    )
    expected_progress_total = scalar(
        cur,
        "select count(*) from study_tasks t join study_plans p on p.id=t.plan_id "
        "where p.owner_id=%s and p.status='active'",
        (owner_id,),
    )
    cur.execute(
        "select status, count(*) from documents where owner_id=%s group by status",
        (owner_id,),
    )
    expected_documents = {str(status): count for status, count in cur.fetchall()}
    if dashboard.get("active_plans_count") != expected_active:
        raise StepFailed(
            "dashboard",
            f"active_plans_count={dashboard.get('active_plans_count')} "
            f"expected={expected_active}",
        )
    if dashboard.get("today_pending_tasks") != expected_today:
        raise StepFailed(
            "dashboard",
            f"today_pending_tasks={dashboard.get('today_pending_tasks')} "
            f"expected={expected_today}",
        )
    if dashboard.get("plan_progress", {}).get("total") != expected_progress_total:
        raise StepFailed(
            "dashboard",
            f"plan_progress.total={dashboard.get('plan_progress', {}).get('total')} "
            f"expected={expected_progress_total}",
        )
    if dashboard.get("document_counts") != expected_documents:
        raise StepFailed(
            "dashboard",
            f"document_counts={dashboard.get('document_counts')} "
            f"expected={expected_documents}",
        )
    passed(
        "dashboard",
        f"active_plans={dashboard['active_plans_count']} "
        f"today_pending={dashboard['today_pending_tasks']} "
        f"progress_total={dashboard['plan_progress']['total']} "
        f"documents={dashboard['document_counts']} match user data",
    )


def cleanup(api, cur, state) -> bool:
    print("--- CLEANUP ---", flush=True)
    cleanup_ok = True

    def delete(step: str, path: str) -> None:
        nonlocal cleanup_ok
        try:
            response = request(api, step, "DELETE", path)
            if response.status_code not in (200, 204, 404):
                cleanup_ok = False
                failed(step, f"HTTP {response.status_code}: {response.text[:200]}")
            else:
                print(f"CLEANUP_DELETE {path} status={response.status_code}", flush=True)
        except Exception as exc:
            cleanup_ok = False
            failed(step, exc)

    session_id = state.get("session_id")
    if session_id:
        delete("cleanup chat session", f"/chat/sessions/{session_id}")

    for note_id in state.get("note_ids", []):
        delete("cleanup note", f"/notes/{note_id}")

    for quiz_id in state.get("quiz_ids", []):
        delete("cleanup quiz", f"/quizzes/{quiz_id}")

    plan_id = state.get("plan_id")
    if plan_id:
        delete("cleanup plan", f"/planner/plans/{plan_id}")

    doc_id = state.get("doc_id")
    page_folders: set[str] = set()
    if doc_id:
        cur.execute(
            "select page_image_key from document_pages where document_id=%s "
            "and page_image_key is not null",
            (doc_id,),
        )
        for (key,) in cur.fetchall():
            if key and "/" in key:
                page_folders.add(key.rsplit("/", 1)[0])
        delete("cleanup document", f"/documents/{doc_id}")

    subject_id = state.get("subject_id")
    if subject_id:
        delete("cleanup subject", f"/subjects/{subject_id}")

    note_ids = state.get("note_ids", [])
    quiz_ids = state.get("quiz_ids", [])
    checks = {
        "subjects": scalar(
            cur, "select count(*) from subjects where id=%s", (subject_id,)
        )
        if subject_id
        else 0,
        "documents": scalar(
            cur, "select count(*) from documents where subject_id=%s", (subject_id,)
        )
        if subject_id
        else 0,
        "pages": scalar(
            cur,
            "select count(*) from document_pages where document_id in "
            "(select id from documents where subject_id=%s)",
            (subject_id,),
        )
        if subject_id
        else 0,
        "chunks": scalar(
            cur,
            "select count(*) from document_chunks where document_id in "
            "(select id from documents where subject_id=%s)",
            (subject_id,),
        )
        if subject_id
        else 0,
        "processing_jobs": scalar(
            cur,
            "select count(*) from processing_jobs where document_id in "
            "(select id from documents where subject_id=%s)",
            (subject_id,),
        )
        if subject_id
        else 0,
        "notes": count_ids(cur, "notes", "id", note_ids),
        "quizzes": count_ids(cur, "quizzes", "id", quiz_ids),
        "quiz_questions": count_ids(cur, "quiz_questions", "quiz_id", quiz_ids),
        "quiz_attempts": count_ids(cur, "quiz_attempts", "quiz_id", quiz_ids),
        "chat_sessions": scalar(
            cur, "select count(*) from chat_sessions where id=%s", (session_id,)
        )
        if session_id
        else 0,
        "chat_messages": scalar(
            cur, "select count(*) from chat_messages where session_id=%s", (session_id,)
        )
        if session_id
        else 0,
        "study_plans": scalar(
            cur, "select count(*) from study_plans where id=%s", (plan_id,)
        )
        if plan_id
        else 0,
        "study_tasks": scalar(
            cur, "select count(*) from study_tasks where plan_id=%s", (plan_id,)
        )
        if plan_id
        else 0,
    }
    print(
        "CLEANUP_DB_COUNTS " + " ".join(f"{k}={v}" for k, v in checks.items()),
        flush=True,
    )
    if any(checks.values()):
        cleanup_ok = False
        failed("cleanup DB rows", str(checks))

    folders: set[str] = set()
    owner_id = state.get("owner_id")
    if doc_id and owner_id:
        folders.add(f"user/{owner_id}/{doc_id}")
    folders |= page_folders
    for folder in sorted(folders):
        try:
            names = list_storage_names(folder)
            print(
                f"CLEANUP_STORAGE folder={folder} objects={len(names)} names={names}",
                flush=True,
            )
            if names:
                cleanup_ok = False
                failed("cleanup storage", f"objects remain: {names}")
        except Exception as exc:
            cleanup_ok = False
            failed("cleanup storage", exc)

    after_counts = {
        "profiles": scalar(cur, "select count(*) from profiles"),
        "subjects": scalar(cur, "select count(*) from subjects"),
        "chat_sessions": scalar(cur, "select count(*) from chat_sessions"),
        "study_plans": scalar(cur, "select count(*) from study_plans"),
    }
    before_counts = state.get("counts_before", {})
    print(
        "COUNTS_BEFORE "
        + " ".join(f"{k}={v}" for k, v in before_counts.items()),
        flush=True,
    )
    print(
        "COUNTS_AFTER " + " ".join(f"{k}={v}" for k, v in after_counts.items()),
        flush=True,
    )
    if before_counts and after_counts != before_counts:
        cleanup_ok = False
        failed("cleanup counts", f"before={before_counts} after={after_counts}")

    if cleanup_ok:
        print("CLEANUP_OK", flush=True)
    else:
        print("CLEANUP_FAILED", flush=True)
    return cleanup_ok


def main() -> int:
    state: dict = {}
    failure: BaseException | None = None
    db = None
    cur = None
    api = None

    try:
        db = db_connect()
        db.autocommit = True
        cur = db.cursor()
        token = login()
        api = httpx.Client(
            base_url=API_BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
        )
        passed("login", "token obtained")

        task0_cleanup(api, cur, state)
        state["counts_before"] = {
            "profiles": scalar(cur, "select count(*) from profiles"),
            "subjects": scalar(cur, "select count(*) from subjects"),
            "chat_sessions": scalar(cur, "select count(*) from chat_sessions"),
            "study_plans": scalar(cur, "select count(*) from study_plans"),
        }
        print(
            "COUNTS_BEFORE "
            + " ".join(f"{k}={v}" for k, v in state["counts_before"].items()),
            flush=True,
        )

        task1_setup(api, cur, state)
        task2_tutor(api, state)
        task3_notes(api, state)
        task4_quizzes(api, cur, state)
        task5_planner(api, cur, state)

    except QuotaExceeded as exc:
        failure = exc
        print(f"STOP_429 | {first_line(exc)}", flush=True)
    except StepFailed as exc:
        failure = exc
        failed(exc.step, exc.message)
    except Exception as exc:
        failure = StepFailed("unexpected", first_line(exc))
        failed("unexpected", exc)

    finally:
        cleanup_ok = True
        if api is not None and cur is not None:
            try:
                cleanup_ok = cleanup(api, cur, state)
            except Exception as exc:
                cleanup_ok = False
                failed("cleanup", exc)
        else:
            print("CLEANUP_SKIPPED (no api/db)", flush=True)

        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
        if api is not None:
            try:
                api.close()
            except Exception:
                pass

    if failure is not None:
        print(f"BATCH_FAILED: {first_line(failure)}", flush=True)
        return 1
    if not cleanup_ok:
        print("BATCH_FAILED: cleanup", flush=True)
        return 1
    print("ALL_PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
