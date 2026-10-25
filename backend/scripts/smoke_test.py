"""PDF-only end-to-end smoke test against the running backend and live Supabase DB.

Only rows and Storage objects created by this script are deleted.
"""
from __future__ import annotations

import asyncio
import math
import os
import sys
import time
from datetime import datetime, timezone
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
SMOKE_QUESTION = os.environ["SMOKE_QUESTION"]
SMOKE_EXPECT_PAGE = int(os.environ["SMOKE_EXPECT_PAGE"])
API_BASE = "http://localhost:8000/api"


class StepFailed(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step
        self.message = message


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


def parse_vector(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    text = str(value).strip()
    if not (text.startswith("[") and text.endswith("]")):
        return None
    return [float(x) for x in text[1:-1].split(",") if x.strip()]


def l2(vec) -> float:
    return math.sqrt(sum(x * x for x in vec))


def cosine(a, b) -> float:
    na, nb = l2(a), l2(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def storage_client():
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def list_storage_names(folder: str) -> list[str]:
    client = storage_client()
    items = client.storage.from_(STORAGE_BUCKET).list(folder)
    return [item.get("name") for item in items if item.get("name")]


def main() -> int:
    subject_id = None
    doc_id = None
    doc_owner_id = None
    doc_storage_key = None
    token = None
    api = None
    db = None
    cur = None
    before_counts = {}
    profile_existed_before = False
    profile_id = None
    auth_endpoint_called = False
    cleanup_ok = True
    failure: StepFailed | None = None

    try:
        try:
            db = db_connect()
            db.autocommit = True
            cur = db.cursor()
            before_counts = {
                "profiles": scalar(cur, "select count(*) from profiles"),
                "subjects": scalar(cur, "select count(*) from subjects"),
                "chat_sessions": scalar(cur, "select count(*) from chat_sessions"),
                "study_plans": scalar(cur, "select count(*) from study_plans"),
            }
            print(
                "COUNTS_BEFORE "
                + " ".join(f"{k}={v}" for k, v in before_counts.items()),
                flush=True,
            )
            profile_id = cur.execute(
                "select id from profiles where email=%s", (SMOKE_EMAIL,)
            )
            row = cur.fetchone()
            profile_id = row[0] if row else None
            profile_existed_before = profile_id is not None
            print(f"SMOKE_PROFILE_EXISTS {int(profile_existed_before)}", flush=True)
            passed("db connect", "select 1 ok; counts captured")
        except Exception as exc:
            failed("db connect", exc)
            raise StepFailed("db connect", first_line(exc))

        try:
            login_url = f"{SUPABASE_URL}/auth/v1/token"
            response = httpx.post(
                login_url,
                params={"grant_type": "password"},
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
                json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
                timeout=30,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"login HTTP {response.status_code}: {response.text[:300]}"
                )
            token = response.json().get("access_token")
            if not token:
                raise RuntimeError("login response did not contain access_token")
            passed("login", "token obtained")
        except Exception as exc:
            failed("login", exc)
            raise StepFailed("login", first_line(exc))

        api = httpx.Client(
            base_url=API_BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
            follow_redirects=True,
        )

        try:
            response = api.get("/health", timeout=20)
            response.raise_for_status()
            if response.json().get("status") != "ok":
                raise RuntimeError(f"unexpected health body: {response.text[:200]}")
            passed("GET /api/health", f"status={response.status_code}")
        except Exception as exc:
            failed("GET /api/health", exc)
            raise StepFailed("GET /api/health", first_line(exc))

        try:
            auth_endpoint_called = True
            response = api.get("/subjects/", timeout=30)
            response.raise_for_status()
            passed(
                "authenticated GET /api/subjects/",
                f"status={response.status_code} subjects={len(response.json())}",
            )
        except Exception as exc:
            failed("authenticated GET /api/subjects/", exc)
            raise StepFailed("authenticated GET /api/subjects/", first_line(exc))

        try:
            smoke_name = (
                "SMOKE TEST "
                + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            )
            response = api.post(
                "/subjects/",
                json={"name": smoke_name},
                timeout=30,
            )
            response.raise_for_status()
            subject_id = response.json()["id"]
            passed("create subject", f"id={subject_id} name={smoke_name}")
        except Exception as exc:
            failed("create subject", exc)
            raise StepFailed("create subject", first_line(exc))

        try:
            pdf_path = Path(SMOKE_PDF)
            if not pdf_path.is_absolute():
                pdf_path = (BACKEND_DIR / pdf_path).resolve()
            if not pdf_path.exists():
                raise FileNotFoundError(f"SMOKE_PDF not found: {pdf_path}")
            pdf_bytes = pdf_path.read_bytes()
            response = api.post(
                "/documents/upload",
                params={"subject_id": subject_id, "doc_type": "pdf"},
                files={
                    "files": (
                        pdf_path.name,
                        pdf_bytes,
                        "application/pdf",
                    )
                },
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json()
            doc_id = payload["id"]
            doc_owner_id = payload["owner_id"]
            row = cur.execute(
                "select storage_key from documents where id=%s", (doc_id,)
            )
            row = cur.fetchone()
            doc_storage_key = row[0] if row else None
            passed(
                "upload PDF",
                f"id={doc_id} status={payload.get('status')} storage_key_set={bool(doc_storage_key)}",
            )
        except Exception as exc:
            failed("upload PDF", exc)
            raise StepFailed("upload PDF", first_line(exc))

        try:
            deadline = time.time() + 180
            status = None
            page_count = 0
            error_message = None
            while time.time() < deadline:
                response = api.get(f"/documents/{doc_id}", timeout=30)
                response.raise_for_status()
                payload = response.json()
                status = payload.get("status")
                page_count = payload.get("page_count", 0)
                error_message = payload.get("error_message")
                if status in ("ready", "failed"):
                    break
                time.sleep(3)
            if status not in ("ready", "failed"):
                raise RuntimeError(f"timeout waiting for document (last status={status})")
            if status == "failed":
                message = first_line(error_message or "no error message")
                print(f"DOCUMENT_FAILED_ERROR: {message}", flush=True)
                failed("poll document", f"status=failed error={message}")
                raise StepFailed("poll document", f"status=failed error={message}")
            passed("poll document", f"status={status} page_count={page_count}")
        except StepFailed:
            raise
        except Exception as exc:
            failed("poll document", exc)
            raise StepFailed("poll document", first_line(exc))

        try:
            cur.execute(
                "select id, page_start, page_end, embedding::text "
                "from document_chunks where document_id=%s "
                "order by page_start, id",
                (doc_id,),
            )
            rows = cur.fetchall()
            if not rows:
                raise RuntimeError("no chunks found for this document")
            chunks = []
            norms = []
            for chunk_id, page_start, page_end, embedding_text in rows:
                vector = parse_vector(embedding_text)
                if vector is None:
                    raise RuntimeError(f"chunk {chunk_id} has NULL/unparseable embedding")
                norm = l2(vector)
                norms.append(norm)
                chunks.append((chunk_id, page_start, page_end, vector))
            if any(norm <= 0.0 for norm in norms):
                raise RuntimeError(
                    f"zero embedding found: min_l2={min(norms):.6f} chunk_count={len(norms)}"
                )
            passed(
                "chunks and embeddings",
                f"chunk_count={len(rows)} min_l2={min(norms):.6f}",
            )
        except Exception as exc:
            failed("chunks and embeddings", exc)
            raise StepFailed("chunks and embeddings", first_line(exc))

        try:
            from app.ai.gemini import GeminiOcrProvider

            provider = GeminiOcrProvider()
            question_vectors = asyncio.run(provider.embed_texts([SMOKE_QUESTION]))
            question_vector = question_vectors[0] if question_vectors else []
            if not question_vector or l2(question_vector) <= 0.0:
                raise RuntimeError("question embedding is empty or zero")
            passed(
                "embed question",
                f"vector_length={len(question_vector)} l2={l2(question_vector):.6f}",
            )
        except Exception as exc:
            failed("embed question", exc)
            raise StepFailed("embed question", first_line(exc))

        try:
            scored = [
                (cosine(question_vector, vector), page_start, chunk_id)
                for chunk_id, page_start, _page_end, vector in chunks
            ]
            similarity, top_page, top_chunk_id = max(scored, key=lambda item: item[0])
            print(
                f"COSINE_TOP page_start={top_page} similarity={similarity:.6f}",
                flush=True,
            )
            if int(top_page) != SMOKE_EXPECT_PAGE:
                raise AssertionError(
                    f"top page {top_page} != expected {SMOKE_EXPECT_PAGE}"
                )
            passed(
                "cosine search",
                f"top_page_start={top_page} similarity={similarity:.6f}",
            )
        except Exception as exc:
            failed("cosine search", exc)
            raise StepFailed("cosine search", first_line(exc))

        try:
            if not doc_storage_key:
                raise RuntimeError("document has no storage_key")
            folder = doc_storage_key.rsplit("/", 1)[0]
            expected_name = doc_storage_key.rsplit("/", 1)[-1]
            names = list_storage_names(folder)
            if expected_name not in names:
                raise RuntimeError(
                    f"expected object {expected_name} not found; present={names}"
                )
            passed("storage object", f"name={expected_name} folder={folder}")
        except Exception as exc:
            failed("storage object", exc)
            raise StepFailed("storage object", first_line(exc))

    except StepFailed as exc:
        failure = exc
    except Exception as exc:
        failure = StepFailed("unexpected", first_line(exc))
        failed("unexpected", exc)

    finally:
        print("--- CLEANUP ---", flush=True)

        storage_folders = set()
        if doc_storage_key and "/" in doc_storage_key:
            storage_folders.add(doc_storage_key.rsplit("/", 1)[0])
        if subject_id and cur is not None:
            try:
                cur.execute(
                    "select storage_key from documents where subject_id=%s",
                    (subject_id,),
                )
                for (key,) in cur.fetchall():
                    if key and "/" in key:
                        storage_folders.add(key.rsplit("/", 1)[0])
            except Exception as exc:
                print(f"CLEANUP_STORAGE_KEY_LOOKUP_ERROR: {first_line(exc)}", flush=True)

        docs_to_delete = set()
        if doc_id:
            docs_to_delete.add(str(doc_id))
        if subject_id and api is not None:
            try:
                response = api.get(
                    "/documents/", params={"subject_id": subject_id}, timeout=30
                )
                if response.status_code == 200:
                    for item in response.json():
                        docs_to_delete.add(str(item["id"]))
            except Exception as exc:
                print(f"CLEANUP_LIST_DOCS_ERROR: {first_line(exc)}", flush=True)

        for document_id in sorted(docs_to_delete):
            if api is None:
                break
            try:
                response = api.delete(f"/documents/{document_id}", timeout=60)
                if response.status_code not in (200, 204, 404):
                    raise RuntimeError(
                        f"delete document HTTP {response.status_code}: {response.text[:200]}"
                    )
                print(
                    f"CLEANUP_DELETE_DOCUMENT id={document_id} status={response.status_code}",
                    flush=True,
                )
            except Exception as exc:
                cleanup_ok = False
                failed("cleanup delete document", exc)

        if db is not None and cur is not None:
            try:
                doc_rows = (
                    scalar(cur, "select count(*) from documents where id=%s", (doc_id,))
                    if doc_id
                    else 0
                )
                chunk_rows = (
                    scalar(
                        cur,
                        "select count(*) from document_chunks where document_id=%s",
                        (doc_id,),
                    )
                    if doc_id
                    else 0
                )
                page_rows = (
                    scalar(
                        cur,
                        "select count(*) from document_pages where document_id=%s",
                        (doc_id,),
                    )
                    if doc_id
                    else 0
                )
                job_rows = (
                    scalar(
                        cur,
                        "select count(*) from processing_jobs where document_id=%s",
                        (doc_id,),
                    )
                    if doc_id
                    else 0
                )
                print(
                    "CLEANUP_DB_COUNTS "
                    f"documents={doc_rows} chunks={chunk_rows} "
                    f"pages={page_rows} processing_jobs={job_rows}",
                    flush=True,
                )
                if doc_rows or chunk_rows or page_rows or job_rows:
                    cleanup_ok = False
                    failed(
                        "cleanup DB rows",
                        f"documents={doc_rows} chunks={chunk_rows} pages={page_rows} processing_jobs={job_rows}",
                    )
            except Exception as exc:
                cleanup_ok = False
                failed("cleanup DB row check", exc)

        for folder in sorted(storage_folders):
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

        if subject_id and api is not None:
            try:
                response = api.delete(f"/subjects/{subject_id}", timeout=60)
                if response.status_code not in (200, 204, 404):
                    raise RuntimeError(
                        f"delete subject HTTP {response.status_code}: {response.text[:200]}"
                    )
                print(
                    f"CLEANUP_DELETE_SUBJECT id={subject_id} status={response.status_code}",
                    flush=True,
                )
            except Exception as exc:
                cleanup_ok = False
                failed("cleanup delete subject", exc)

        if (
            not profile_existed_before
            and auth_endpoint_called
            and db is not None
            and cur is not None
        ):
            try:
                cur.execute("select id from profiles where email=%s", (SMOKE_EMAIL,))
                row = cur.fetchone()
                created_profile_id = row[0] if row else None
                if created_profile_id:
                    dependents = sum(
                        scalar(
                            cur,
                            f"select count(*) from {table} where {column}=%s",
                            (created_profile_id,),
                        )
                        for table, column in (
                            ("subjects", "owner_id"),
                            ("documents", "owner_id"),
                            ("chat_sessions", "owner_id"),
                            ("study_plans", "owner_id"),
                        )
                    )
                    if dependents == 0:
                        cur.execute(
                            "delete from profiles where id=%s", (created_profile_id,)
                        )
                        print("CLEANUP_AUTO_PROFILE_DELETED yes", flush=True)
                    else:
                        cleanup_ok = False
                        print(
                            f"CLEANUP_AUTO_PROFILE_KEPT dependents={dependents}",
                            flush=True,
                        )
            except Exception as exc:
                cleanup_ok = False
                failed("cleanup auto-provisioned profile", exc)

        if db is not None and cur is not None:
            try:
                after_counts = {
                    "profiles": scalar(cur, "select count(*) from profiles"),
                    "subjects": scalar(cur, "select count(*) from subjects"),
                    "chat_sessions": scalar(cur, "select count(*) from chat_sessions"),
                    "study_plans": scalar(cur, "select count(*) from study_plans"),
                }
                print(
                    "COUNTS_AFTER "
                    + " ".join(f"{k}={v}" for k, v in after_counts.items()),
                    flush=True,
                )
                if after_counts != before_counts:
                    cleanup_ok = False
                    failed(
                        "cleanup other data counts",
                        f"before={before_counts} after={after_counts}",
                    )
            except Exception as exc:
                cleanup_ok = False
                failed("cleanup counts", exc)

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

        if cleanup_ok:
            print("CLEANUP_OK", flush=True)
        else:
            print("CLEANUP_FAILED", flush=True)

    if failure is not None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
