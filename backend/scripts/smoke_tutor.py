"""Live smoke test: tutor citations + planner dashboard.

Creates one SMOKE TEST <timestamp> subject, an in-memory 8-page PDF, a tutor
session and a plan. Deletes only what it creates. Any 429/quota response stops
the run; cleanup runs in ``finally``.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import fitz
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

API_BASE = "http://localhost:8000/api"
HTTP_TIMEOUT = 180.0
PROCESS_TIMEOUT = 300.0
SUBJECT_PREFIX = "SMOKE TEST"
DOC_NAME = "smoke_tutor.pdf"

PAGE_FACTS = [
    "The Aurelian telescope was completed in 1904 by inventor Sela Vorn.",
    "The Brythian bridge uses 3,412 hand-cut stones.",
    "The Cindral library stores 82,000 scrolls in underground vaults.",
    "The Draven comet returns every 47 years.",
    "The Zorvian archive was founded in 1873 by Maris Telk.",
    "The Erevos engine runs on compressed moss.",
    "The Fennic observatory sits 2,860 meters above sea level.",
    "The Gormath treaty was signed on 11 April 1652.",
]

PAGE_TEXTS = [
    "The Aurelian telescope is a fictional instrument described in the archives of the northern observatory. "
    "Its designers wanted a wide field of view rather than extreme magnification, so they arranged six curved "
    "mirrors in a shallow arc. The structure was assembled in a coastal workshop where salt air made maintenance "
    "difficult. Volunteers polished each mirror by hand over several months. The instrument was first pointed at "
    "the evening sky during a public festival, and visitors described the image as surprisingly bright. Its mount "
    "allowed slow tracking of the stars without motors. Modern students study the Aurelian telescope as an example "
    "of careful mechanical design. " + PAGE_FACTS[0] + " Records note that the original wooden crate still "
    "survives in a museum basement. The project cost less than expected because most parts were reused from "
    "earlier experiments. Its nickname among local historians is the gentle eye of the north.",
    "The Brythian bridge crosses a narrow river in the hill country of the invented province of Oren. Its builders "
    "chose stone because the river floods quickly in spring. Teams worked from both banks and met in the middle "
    "after two years. The roadway is wide enough for two carts, and the parapets are low so travelers can see the "
    "water. Local stories claim that a bell was hung beneath the central arch to warn of high water. Engineers "
    "admire the bridge for its simple drainage channels and its careful foundations. " + PAGE_FACTS[1] + " Each "
    "stone was numbered before placement, and a copy of the numbering list is kept in the town hall. Visitors "
    "often stop at the eastern end to sketch the arch. The bridge remains in daily use and is inspected every "
    "autumn.",
    "The Cindral library occupies a small building beside a public garden, but most of its collection lies "
    "underground. Readers enter through a quiet hall with wooden desks and lamps. A narrow stair leads to vaults "
    "cut into soft rock. The air there stays cool and dry throughout the year. Librarians use hand carts to move "
    "boxes between rooms. The oldest items are wrapped in cloth and checked only by appointment. " + PAGE_FACTS[2]
    + " A catalog painted on the wall lists each vault by number and subject. Students are allowed to request "
    "three items per day. The library closes during the hottest weeks so that the vaults can be inspected. Its "
    "staff includes two conservators and a small team of volunteers.",
    "The Draven comet is a periodic visitor invented for the astronomy records of the southern islands. Observers "
    "first recorded it as a faint smudge near the horizon. Later calculations showed that its orbit is highly "
    "elliptical and tilted relative to the planets. The comet brightens quickly as it approaches the inner solar "
    "system. Its tail has been described as thin and blue-green in small telescopes. Amateur astronomers organize "
    "viewing nights when the return is expected. " + PAGE_FACTS[3] + " Records from the last apparition include "
    "sketches, photographs, and a detailed table of positions. Scientists use these old notes to refine the orbit "
    "for future predictions. The next return is already marked on several calendars. Public talks about the comet "
    "often fill the local lecture hall.",
    "The Zorvian archive is a fictional collection of letters, maps, and official records kept in a converted "
    "warehouse. Its reading room has long tables and tall windows that face a courtyard. Visitors must sign a "
    "register before requesting a box. Staff members wear gloves when handling fragile paper. The archive "
    "organizes its holdings by region and year rather than by donor. A small conservation lab repairs tears and "
    "removes rust from old fasteners. " + PAGE_FACTS[4] + " The first catalog listed only twelve boxes, but the "
    "collection grew quickly through donations. Researchers value the archive for its detailed land surveys and "
    "family correspondence. The building was expanded twice without changing its outer walls. A fire in the north "
    "wing was contained before it reached the shelves.",
    "The Erevos engine is a fictional machine built to demonstrate an unusual source of power. Its inventor "
    "argued that compressed moss could store energy safely in small cylinders. The engine has a rounded body, "
    "brass fittings, and a large flywheel. During demonstrations, it turns a belt that lifts a small weight. "
    "Visitors often ask why the machine is so quiet compared with other engines. The answer is that the moss "
    "releases energy slowly through a regulated valve. " + PAGE_FACTS[5] + " A gauge on the side shows the "
    "remaining pressure, and a second gauge records temperature. The machine was never used for heavy work "
    "because its output was modest. It survives today in a technical museum, where it is operated twice a year. "
    "Children enjoy watching the flywheel spin.",
    "The Fennic observatory stands on a rocky ridge above the cloud line. The road to the site is steep and "
    "closes in winter. The main dome houses a reflecting telescope with a wide base. A smaller building contains "
    "workshops, a kitchen, and beds for visiting researchers. The air is thin and cold, so observers work in short "
    "shifts. " + PAGE_FACTS[6] + " This height reduces atmospheric blur and gives very clear images on calm "
    "nights. The staff keep a log of weather, equipment faults, and unusual sightings. Power comes from a "
    "generator and a small bank of batteries. Supplies are carried up by a tracked vehicle. The observatory is "
    "named after a fictional explorer who mapped the ridge.",
    "The Gormath treaty is a fictional agreement between two neighboring regions that shared a river. "
    "Negotiators met in a stone hall with a single round table. The talks lasted several weeks and focused on "
    "fishing rights, tolls, and the repair of a damaged bridge. Each side brought clerks who wrote down every "
    "proposal. The final document was copied by hand and sealed with wax. " + PAGE_FACTS[7] + " Its main clauses "
    "set aside a stretch of water for quiet fishing and required both regions to share the cost of dredging. A "
    "later amendment added rules for ferries. Historians study the treaty because it includes one of the earliest "
    "written schedules for bridge maintenance. The original copy is kept in a locked cabinet. A modern "
    "translation is displayed in the town museum.",
]


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
        raise StepFailed(step, f"HTTP {response.status_code}: {response.text[:300]}")
    return response


def login() -> str:
    response = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
        timeout=HTTP_TIMEOUT,
    )
    if response.status_code != 200:
        raise StepFailed("login", f"HTTP {response.status_code}: {response.text[:300]}")
    token = response.json().get("access_token")
    if not token:
        raise StepFailed("login", "login response did not contain access_token")
    return token


def storage_client():
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def list_storage_names(folder: str) -> list[str]:
    client = storage_client()
    items = client.storage.from_(STORAGE_BUCKET).list(folder)
    return [item.get("name") for item in items if item.get("name")]


def build_pdf() -> bytes:
    document = fitz.open()
    try:
        for text in PAGE_TEXTS:
            page = document.new_page()
            inserted = page.insert_textbox(
                fitz.Rect(50, 50, 545, 792),
                text,
                fontsize=11,
                fontname="helv",
            )
            if inserted < 0:
                raise StepFailed("build PDF", "page text did not fit")
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()


def citation_pages(citations: list[dict]) -> list[str]:
    return [
        f"{c.get('document_name')} p{c.get('page_start')}-{c.get('page_end')}"
        for c in citations
    ]


def includes_page(citations: list[dict], page: int) -> bool:
    return any(
        int(c.get("page_start") or 0) <= page <= int(c.get("page_end") or 0)
        for c in citations
    )


def ask(api, session_id: str, subject_id: str, step: str, question: str) -> dict:
    response = expect(
        step,
        request(
            api,
            step,
            "POST",
            f"/chat/sessions/{session_id}/messages",
            json={"content": question, "subject_id": subject_id},
        ),
        (201,),
    )
    return response.json()


def task_a_setup(api, cur, state) -> None:
    name = f"{SUBJECT_PREFIX} {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    subject = expect(
        "create subject",
        request(api, "create subject", "POST", "/subjects/", json={"name": name}),
        (201,),
    ).json()
    state["subject_id"] = subject["id"]

    pdf_bytes = build_pdf()
    for index, text in enumerate(PAGE_TEXTS, start=1):
        words = len(text.split())
        if not 120 <= words <= 190:
            raise StepFailed("build PDF", f"page {index} has {words} words")
        if PAGE_FACTS[index - 1] not in text:
            raise StepFailed("build PDF", f"page {index} missing its fact")

    upload = expect(
        "upload PDF",
        request(
            api,
            "upload PDF",
            "POST",
            "/documents/upload",
            params={"subject_id": subject["id"], "doc_type": "pdf"},
            files={"files": (DOC_NAME, pdf_bytes, "application/pdf")},
        ),
        (201,),
    ).json()
    state["doc_id"] = upload["id"]
    state["owner_id"] = upload["owner_id"]
    state["doc_name"] = upload["name"]

    started = time.time()
    deadline = started + PROCESS_TIMEOUT
    status = None
    page_count = 0
    error_message = None
    while time.time() < deadline:
        document = expect(
            "poll document",
            request(api, "poll document", "GET", f"/documents/{upload['id']}"),
            (200,),
        ).json()
        status = document.get("status")
        page_count = document.get("page_count", 0)
        error_message = document.get("error_message")
        if status in ("ready", "failed"):
            break
        time.sleep(3)
    elapsed = time.time() - started
    if status != "ready":
        raise StepFailed(
            "poll document",
            f"status={status} seconds={elapsed:.1f} error={first_line(error_message or 'none')}",
        )

    chunks = expect(
        "load chunks",
        request(api, "load chunks", "GET", f"/documents/{upload['id']}/chunks"),
        (200,),
    ).json()
    if not chunks:
        raise StepFailed("load chunks", "document has no chunks")
    if page_count != 8:
        raise StepFailed("poll document", f"expected 8 pages, got {page_count}")
    state["chunks"] = {str(c["id"]): c for c in chunks}
    passed(
        "(a) PDF ready",
        f"name={state['doc_name']} page_count={page_count} chunk_count={len(chunks)} "
        f"seconds={elapsed:.1f}",
    )


def task_b_citation(api, state) -> None:
    session = expect(
        "create chat session",
        request(
            api,
            "create chat session",
            "POST",
            "/chat/sessions",
            json={"subject_id": state["subject_id"], "title": f"{SUBJECT_PREFIX} tutor"},
        ),
        (201,),
    ).json()
    state["session_id"] = session["id"]

    message = ask(
        api,
        session["id"],
        state["subject_id"],
        "tutor page-5 fact",
        "When was the Zorvian archive founded, and who founded it?",
    )
    answer = message.get("content") or ""
    citations = message.get("citations") or []
    pages = citation_pages(citations)
    lower = answer.lower()
    has_fact = "1873" in lower and "maris telk" in lower
    print(
        f"Q1 answer_length={len(answer)} citations={pages} has_fact={has_fact}",
        flush=True,
    )
    if not citations:
        raise StepFailed("tutor page-5 fact", "answer had no citations")
    if not includes_page(citations, 5):
        raise StepFailed("tutor page-5 fact", f"citations did not include page 5: {pages}")
    if not has_fact:
        raise StepFailed("tutor page-5 fact", f"answer missing fact: {answer[:160]!r}")
    if any(c.get("document_name") != state["doc_name"] for c in citations):
        raise StepFailed("tutor page-5 fact", f"unexpected document names: {pages}")
    passed(
        "(b) tutor page-5 citation",
        f"document={state['doc_name']} citation_pages={pages} "
        f"answer_has_1873_and_Maris_Telk=True",
    )


def task_c_insufficient(api, state) -> None:
    message = ask(
        api,
        state["session_id"],
        state["subject_id"],
        "tutor insufficient",
        "What is the boiling point of water on Mars?",
    )
    answer = message.get("content") or ""
    citations = message.get("citations") or []
    lower = answer.lower()
    says_not_covered = any(
        phrase in lower
        for phrase in ("enough information", "do not cover", "don't cover", "not cover")
    )
    print(
        f"Q2 is_insufficient={message.get('is_insufficient')} citations={len(citations)} "
        f"answer={answer[:120]!r}",
        flush=True,
    )
    if not message.get("is_insufficient"):
        raise StepFailed("tutor insufficient", "is_insufficient was not true")
    if citations:
        raise StepFailed("tutor insufficient", f"citations were not empty: {citation_pages(citations)}")
    if not says_not_covered:
        raise StepFailed("tutor insufficient", f"answer did not say materials are insufficient: {answer[:160]!r}")
    passed(
        "(c) tutor insufficient evidence",
        f"is_insufficient=True citations=0 says_materials_insufficient=True "
        f"answer={answer[:80]!r}",
    )


def task_d_followup(api, state) -> None:
    message = ask(
        api,
        state["session_id"],
        state["subject_id"],
        "tutor follow-up page 2",
        "As a follow-up, how many hand-cut stones does the Brythian bridge use?",
    )
    answer = message.get("content") or ""
    citations = message.get("citations") or []
    pages = citation_pages(citations)
    lower = answer.lower()
    has_fact = "3,412" in lower or "3412" in lower
    print(
        f"Q3 answer_length={len(answer)} citations={pages} has_fact={has_fact}",
        flush=True,
    )
    if not citations:
        raise StepFailed("tutor follow-up page 2", "answer had no citations")
    if not includes_page(citations, 2):
        raise StepFailed("tutor follow-up page 2", f"citations did not include page 2: {pages}")
    passed(
        "(d) tutor follow-up page-2 citation",
        f"citation_pages={pages} answer_has_3412={has_fact}",
    )


def task_e_dashboard(api, cur, state) -> None:
    today = date.today()
    exam = today + timedelta(days=14)
    topics = ["Invented history", "Bridge engineering", "Archive methods"]
    plan = expect(
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
                "preferred_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "topics": topics,
            },
        ),
        (201,),
    ).json()
    state["plan_id"] = plan["id"]

    tasks = expect(
        "generate schedule",
        request(
            api,
            "generate schedule",
            "POST",
            f"/planner/plans/{plan['id']}/generate",
        ),
        (200,),
    ).json()
    if not tasks:
        raise StepFailed("generate schedule", "no tasks generated")

    dashboard = expect(
        "dashboard",
        request(api, "dashboard", "GET", "/planner/dashboard"),
        (200,),
    ).json()
    required = (
        "upcoming_exams",
        "today_tasks",
        "recent_documents",
        "recent_quizzes",
    )
    missing = [key for key in required if key not in dashboard]
    if missing:
        raise StepFailed("dashboard", f"missing keys: {missing}")
    for key in required:
        if not isinstance(dashboard[key], list):
            raise StepFailed("dashboard", f"{key} is not a list")

    owner = state["owner_id"]
    if plan["id"] not in [e.get("id") for e in dashboard["upcoming_exams"]]:
        raise StepFailed("dashboard", "created plan missing from upcoming_exams")
    our_exam = next(e for e in dashboard["upcoming_exams"] if e.get("id") == plan["id"])
    if our_exam.get("days_left") != 14:
        raise StepFailed("dashboard", f"days_left={our_exam.get('days_left')} expected=14")

    if state["doc_id"] not in [d.get("id") for d in dashboard["recent_documents"]]:
        raise StepFailed("dashboard", "uploaded document missing from recent_documents")

    exam_ids = [e.get("id") for e in dashboard["upcoming_exams"]]
    task_ids = [t.get("id") for t in dashboard["today_tasks"]]
    doc_ids = [d.get("id") for d in dashboard["recent_documents"]]
    attempt_ids = [a.get("id") for a in dashboard["recent_quizzes"]]

    def count_owned(table: str, column: str, owner_column: str, ids: list[str]) -> int:
        if not ids:
            return 0
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"select count(*) from {table} where {column} in ({placeholders}) "
            f"and {owner_column}=%s",
            tuple(ids) + (owner,),
        )
        return cur.fetchone()[0]

    owned = {
        "upcoming_exams": count_owned("study_plans", "id", "owner_id", exam_ids),
        "today_tasks": count_owned(
            "study_tasks t join study_plans p on p.id=t.plan_id",
            "t.id",
            "p.owner_id",
            task_ids,
        ),
        "recent_documents": count_owned("documents", "id", "owner_id", doc_ids),
        "recent_quizzes": count_owned("quiz_attempts", "id", "user_id", attempt_ids),
    }
    for key, owned_count in owned.items():
        if owned_count != len(dashboard[key]):
            raise StepFailed("dashboard", f"{key} contained other users' rows: {owned}")
    passed(
        "(e) planner dashboard",
        f"http=200 keys={list(required)} upcoming_exams={len(exam_ids)} "
        f"today_tasks={len(task_ids)} recent_documents={len(doc_ids)} "
        f"recent_quizzes={len(attempt_ids)} all_owner_scoped=True "
        f"our_plan_days_left=14",
    )


def cleanup(api, cur, state) -> bool:
    print("--- CLEANUP ---", flush=True)
    ok = True

    def delete(step: str, path: str) -> None:
        nonlocal ok
        try:
            response = request(api, step, "DELETE", path)
            if response.status_code not in (200, 204, 404):
                ok = False
                failed(step, f"HTTP {response.status_code}: {response.text[:200]}")
            else:
                print(f"CLEANUP_DELETE {path} status={response.status_code}", flush=True)
        except Exception as exc:
            ok = False
            failed(step, exc)

    session_id = state.get("session_id")
    plan_id = state.get("plan_id")
    doc_id = state.get("doc_id")
    subject_id = state.get("subject_id")
    owner_id = state.get("owner_id")

    if session_id:
        delete("cleanup chat session", f"/chat/sessions/{session_id}")
    if plan_id:
        delete("cleanup plan", f"/planner/plans/{plan_id}")
    if doc_id:
        delete("cleanup document", f"/documents/{doc_id}")
    if subject_id:
        delete("cleanup subject", f"/subjects/{subject_id}")

    checks = {
        "subjects": scalar(cur, "select count(*) from subjects where id=%s", (subject_id,))
        if subject_id
        else 0,
        "documents": scalar(cur, "select count(*) from documents where id=%s", (doc_id,))
        if doc_id
        else 0,
        "pages": scalar(
            cur, "select count(*) from document_pages where document_id=%s", (doc_id,)
        )
        if doc_id
        else 0,
        "chunks": scalar(
            cur, "select count(*) from document_chunks where document_id=%s", (doc_id,)
        )
        if doc_id
        else 0,
        "processing_jobs": scalar(
            cur, "select count(*) from processing_jobs where document_id=%s", (doc_id,)
        )
        if doc_id
        else 0,
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
        ok = False
        failed("cleanup DB rows", str(checks))

    if doc_id and owner_id:
        folder = f"user/{owner_id}/{doc_id}"
        try:
            names = list_storage_names(folder)
            print(
                f"CLEANUP_STORAGE folder={folder} objects={len(names)} names={names}",
                flush=True,
            )
            if names:
                ok = False
                failed("cleanup storage", f"objects remain: {names}")
        except Exception as exc:
            ok = False
            failed("cleanup storage", exc)

    after_counts = {
        "profiles": scalar(cur, "select count(*) from profiles"),
        "subjects": scalar(cur, "select count(*) from subjects"),
        "chat_sessions": scalar(cur, "select count(*) from chat_sessions"),
        "study_plans": scalar(cur, "select count(*) from study_plans"),
    }
    before_counts = state.get("counts_before", {})
    print(
        "COUNTS_BEFORE " + " ".join(f"{k}={v}" for k, v in before_counts.items()),
        flush=True,
    )
    print(
        "COUNTS_AFTER " + " ".join(f"{k}={v}" for k, v in after_counts.items()),
        flush=True,
    )
    if before_counts and after_counts != before_counts:
        ok = False
        failed("cleanup counts", f"before={before_counts} after={after_counts}")

    if ok:
        passed(
            "(f) cleanup",
            f"created rows=0 storage_objects=0 "
            f"counts_before={before_counts} counts_after={after_counts}",
        )
        print("CLEANUP_OK", flush=True)
    else:
        print("CLEANUP_FAILED", flush=True)
    return ok


def main() -> int:
    state: dict = {}
    failure: BaseException | None = None
    db = None
    cur = None
    api = None
    cleanup_ok = True

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

        task_a_setup(api, cur, state)
        task_b_citation(api, state)
        task_c_insufficient(api, state)
        task_d_followup(api, state)
        task_e_dashboard(api, cur, state)

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
        print(f"SMOKE_FAILED: {first_line(failure)}", flush=True)
        return 1
    if not cleanup_ok:
        print("SMOKE_FAILED: cleanup", flush=True)
        return 1
    print("ALL_PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
