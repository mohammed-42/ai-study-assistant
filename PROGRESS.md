# AI Study Assistant — PROGRESS

## Current state

- **Phase:** 7 — Hardening. Code complete; live verification partial (Gemini daily quota blocks final planner rerun).
- **Live verification:** tutor, notes, quizzes LIVE-VERIFIED; planner PARTIAL; full smoke stopped on Gemini 429 daily quota.
- **Backend tests:** 184/184 passing (mocked/hermetic).
- **Frontend:** `tsc --noEmit` and `npm run build` clean.
- **Latest commit:** pending `feat: settings, account deletion, not-found page, route aliases`.
- **Session:** Paused on 2026-10-26 after Gemini free-tier quota exhaustion; resume by rerunning `backend/scripts/smoke_features.py` after quota reset.
- **Last updated:** 2026-11-01

---

## Phase checklist

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Foundation: config, DB models, auth, subjects CRUD, frontend shell | DONE |
| 2 | Documents: upload, pages/chunks, processing pipeline, UI | DONE |
| 3 | OCR: Gemini vision + optional Tesseract, page edit/re-embed | DONE |
| 4 | Tutor: RAG retrieval, grounded answers with citations, chat UI | DONE |
| 5 | Notes + Quizzes: generation, grading, attempts, UI | DONE |
| 6 | Planner + Dashboard: rule-based schedule, tasks, stats | DONE |
| 7 | Hardening: rate limits, signed URLs, storage cleanup, resilience, docs | Code complete; live verification partial (Gemini daily quota) |

OCR uses Gemini vision through `settings.GEMINI_MODEL` (default `gemini-3.6-flash`).

---

## Phase 7 — Hardening

| Item | Status | Evidence |
|------|--------|----------|
| Backend suite | UNIT-TESTED (mocked) | `pytest -q` -> 184 passed in 53.17s |
| Frontend typecheck + build | UNIT-TESTED (mocked) | `tsc` exit 0; `npm run build` exit 0 |
| Git-history secret scan | LIVE-VERIFIED | Only `.env.example` files tracked; no `AIza`, `sb_secret_`, or `eyJ` in history; no rotation needed |
| README + upload notices | UNIT-TESTED (mocked) | README setup/run/test/limitations; Documents page shows OCR accuracy and Gemini privacy notices in a `role="note"` block; browser UI NOT VERIFIED |
| Rate limits (upload, AI, re-embed) | UNIT-TESTED (mocked) | `tests/test_rate_limit.py`; process-local |
| Signed page-image URLs | UNIT-TESTED (mocked) | `tests/test_storage_security.py` |
| Storage upload/delete wiring | UNIT-TESTED (mocked) | storage tests; rendered page images are included by folder cleanup (`test_delete_document_removes_rendered_page_images`); live storage path exercised by PDF/handwriting smoke |
| Document readiness gating | UNIT-TESTED (mocked) | Ready only with ≥1 page, non-empty text, ≥1 chunk, all embeddings non-zero |
| Embedding failure handling | UNIT-TESTED (mocked) | `embed_texts` raises; failed docs persist no chunks/zero vectors |
| No-readable-text handling | UNIT-TESTED (mocked) | 0 pages, all-empty pages, and `[NO_TEXT]` → failed |
| Scanned-PDF rendering at 200 DPI | UNIT-TESTED (mocked) | `test_scanned_pdf_renders_at_200_dpi`, `test_mixed_pdf_uses_text_layer_then_ocr`, `test_scanned_pdf_saves_page_image_and_text_page_has_none` (JPEG quality 85, document-folder key, text page None) |
| OCR/embedding provider error mapping | UNIT-TESTED (mocked) | `test_quota_error_fails_clearly_and_retry_succeeds`, `test_timeout_maps_to_busy_message`, `test_empty_ocr_text_is_no_readable_text`, `test_failed_ocr_pages_do_not_count_toward_daily_limit` |
| OCR per-document and daily limits | UNIT-TESTED (mocked) | `test_over_per_document_ocr_cap_fails_without_calling_ocr`, `test_scanned_pdf_over_daily_limit_fails_without_calling_ocr`, `test_ocr_exactly_at_per_document_cap_passes` |
| Re-run OCR for one page | LIVE-VERIFIED | Live handwriting smoke: upload status=uploaded/ready in 31.8s; rerun-ocr HTTP 200; new text length=207; old_chunks_remaining=0; new_chunk_count=1 min_l2=0.590280; cleanup documents/chunks/pages/jobs=0 and profiles/subjects/chat_sessions/study_plans equal (3/2/2/1). Mocked tests: `test_rerun_ocr_replaces_text_and_chunks`, `test_rerun_ocr_failure_keeps_old_text_and_chunks`, `test_rerun_ocr_quota_returns_503_and_keeps_old_data`, `test_rerun_ocr_embedding_failure_keeps_old_text_and_chunks`, `test_rerun_ocr_other_user_gets_404`, `test_rerun_ocr_page_without_image_gets_400`, `test_rerun_ocr_daily_limit_reached`, `test_rerun_ocr_succeeds_for_scanned_pdf_page` |
| Cross-user isolation | UNIT-TESTED (mocked) | `tests/test_isolation.py` (19 tests): users A/B across documents, pages, chunks, page image URL, rerun-ocr, chat sessions/messages, notes, quizzes/attempts, study plans/tasks; unauthenticated and garbage-token requests return 401. Fixed planner dashboard leak of other users' today tasks. |
| Chunk page mapping | UNIT-TESTED (mocked) | `tests/test_chunk_pages.py` (3 tests): three-page text verifies chunks inside one page, across two pages, and across three pages; chunk size/overlap behavior unchanged. |
| Retry after embedding failure | UNIT-TESTED (mocked) | Retry reaches ready without duplicate chunks |
| Processing job state | IMPLEMENTED | Jobs set completed/failed; smoke cleanup shows 0 job rows |
| PDF text extraction (PyMuPDF) | LIVE-VERIFIED | fitz 1.28.2 opened `samples/sample.pdf`: 3 pages, chars `[1935, 2198, 1205]` |
| DB pooler | LIVE-VERIFIED | Connection succeeded; issue RESOLVED (wrong pooler host prefix and a password with special characters) |
| Alembic upgrade + HNSW index | LIVE-VERIFIED | Stamped and upgraded to `b7d41e9a2c63`; HNSW index present |
| FK cascades | LIVE-VERIFIED | Cascade deletes confirmed against live DB |
| JWKS | LIVE-VERIFIED | Key fetched from configured JWKS endpoint |
| Gemini text, vision, embedding | LIVE-VERIFIED | Text and vision passed; `gemini-embedding-001` returned 768 dims with `output_dimensionality=768` |
| Supabase login | LIVE-VERIFIED | Login succeeded |
| End-to-end smoke test | PARTIAL | Batch 2 live smoke: PDF upload ready (3 pages, 2 chunks), tutor/notes/quizzes LIVE-VERIFIED, planner PARTIAL; cleanup rows/storage=0 and counts before=after in the tutor/notes/quizzes runs; one planner run left a chat session after a transient connection reset (manually cleaned). Final rerun stopped at tutor with Gemini daily quota 429 (20/day), so the full-script planner dashboard check was not repeated. Logs: `logs/step10_features_retry*.log`, `logs/server_step10.err.log`. |
| Tailwind 3 compatibility | UNIT-TESTED (mocked) | No v4-only utility matches remain; `tailwindcss 3.4.10` build exit 0; CSS contains card spacing, 3px ring, 2px blur, `has-`/`data-` variants |
| Upload dialog | NOT VERIFIED | New dialog supports one PDF or 2-20 images, reorder/remove, client validation, status polling, and privacy/OCR notices; `tsc`/build exit 0; browser UI not exercised |
| Quiz + notes generate dialog | UNIT-TESTED (mocked) | Subject select is required; optional document select lists only that subject's READY documents; unset `subject_id`/`document_id` are omitted (never empty strings); backend 422 message asserted for both routes; valid `subject_id` passes with Gemini mocked; `tsc`/build exit 0; browser UI NOT VERIFIED |
| Responsive page layout | NOT VERIFIED | Header/action rows stack below `sm`; long titles wrap; documents table scrolls horizontally; `tsc`/build exit 0; browser UI not exercised |
| Document retry/delete/filter/pagination | UNIT-TESTED (mocked) | Backend list accepts `subject_id`/`limit`/`offset`; defaults preserve unpaginated behavior (`test_list_documents_paginated`, `test_list_documents_filtered_pagination`). Subject filtering is server-side before pagination. Documents page adds 10-row pagination, failed-only retry with error text and polling, delete confirmation; detail header adds failed-only retry and delete with polling. `tsc`/build exit 0; browser UI NOT VERIFIED |
| Scanned PDF page images + side-by-side review | UNIT-TESTED (mocked) | OCR-rendered PDF pages are saved as JPEG quality 85 under `user/<owner>/<document>/page_<n>.jpg`; text-layer pages have no image; rerun OCR succeeds from the saved image; document delete removes page images. DocumentDetail shows the signed image left and text/controls right, with skeleton, retry, full-size link, and vertical stacking below `md`. `tsc`/build exit 0; browser UI NOT VERIFIED |
| Settings, account deletion, not-found, aliases | UNIT-TESTED (mocked) | `PUT /api/profile` trims/validates full name, ignores email changes, and updates only the current user; `GET /api/profile` returns the current profile. `DELETE /api/account` removes user storage objects, deletes the profile (FK cascade), then deletes the Supabase auth user with the backend-only service role key; storage/auth failures return explicit messages describing any partial state. Settings page has read-only email, editable full name, log out, and typed `DELETE` confirmation; sidebar Settings link, not-found page, and `/dashboard` + `/study-planner` aliases added. `pytest -q` -> 184 passed in 53.17s; `tsc` exit 0; `npm run build` exit 0; no live calls; browser UI NOT VERIFIED |
| Migrations on a blank DB | NOT VERIFIED | — |
| Tutor against real Gemini | LIVE-VERIFIED | `smoke_features.py`: "What is a component?" -> answer_length=187, citations=1 (`sample.pdf p1`); off-topic question -> `is_insufficient=True`, citations=0; follow-up -> answer_length=385, citations=1. |
| Resolved tutor citations | UNIT-TESTED (mocked) | `tests/test_citations.py`: database resolves document name, page range, OCR/needs_review/user_edited flags; invalid/foreign chunk IDs dropped; API and history return citation objects, not chunk IDs. Browser UI NOT VERIFIED. |
| Tutor streaming endpoint | NOT IMPLEMENTED | Frontend never used `/messages/stream`; removed unused endpoint and `stream` parameter. No streaming test remains. |
| Notes against real Gemini | LIVE-VERIFIED | Summary/key_concepts/definitions/revision all HTTP 201, content lengths 1565/1790/1596/4124, saved=True, raw_json=False; edit persisted; delete HTTP 204 then GET 404. |
| Quizzes against real Gemini | LIVE-VERIFIED | Generate/list/get hide `correct_option_index`, `model_answer`, `explanation`; mixed quiz 3 questions; all-correct=100, all-wrong=0; summary attempts=2 avg=50.0 best=100; short-answer paraphrase correct, unrelated answer incorrect. |
| Planner against real Gemini | PARTIAL | Create plan, generate 3 tasks (max 45 min/day, within exam window), mark done, regenerate preserved completed. Observed duplicate pending topics before fix; dashboard returned HTTP 500 in full run (transient), targeted dashboard returned 200 with `active_plans=1`, `today_pending=2`, `progress total=5 completed=1` after. Regenerate fix unit-tested; full-script dashboard rerun blocked by Gemini daily quota. |
| Browser UI test | NOT VERIFIED | — |

### Step 5 — readiness and embedding failures

- A document becomes `ready` only when it has ≥1 page, at least one non-empty page, ≥1 chunk, and every chunk has a non-zero embedding.
- `embed_texts` now raises after bounded retries instead of returning zero vectors.
- Embedding failure deletes persisted chunks and marks the document `failed` with `Embedding service unavailable. Please retry.`
- 0 pages, all-empty pages, or OCR returning only `[NO_TEXT]` marks the document `failed` with `No readable text was found in this file.`
- A missing Gemini key marks the document `failed` with a clear configuration message.
- Processing jobs are marked completed/failed; reprocessing after an embedding failure clears old chunks and does not duplicate them.
- Tests: `118 passed in 21.73s`; PDF and handwriting smoke tests passed with cleanup.

### Live verification log

- DB connection: LIVE-VERIFIED. Pooler issue RESOLVED — cause was a wrong pooler host prefix and a password with special characters.
- Alembic stamped and upgraded to `b7d41e9a2c63`; HNSW index LIVE-VERIFIED.
- FK cascades: LIVE-VERIFIED.
- JWKS key: LIVE-VERIFIED.
- Gemini text, vision and 768-dim embedding: LIVE-VERIFIED.
- Supabase login: LIVE-VERIFIED.
- PDF smoke: LIVE-VERIFIED — 3 pages, 2 chunks, min_l2=0.589452, signed URL 200, private URL 400, cleanup OK.
- Handwriting smoke: LIVE-VERIFIED — 1 OCR page, 1 chunk, min_l2=0.592292, edit/re-embed marker top, cleanup OK.
- Step 6 PDF smoke: LIVE-VERIFIED — ready, 3 pages, 2 chunks, min_l2=0.589452, cleanup OK.
- Step 6 handwriting rerun-OCR: NOT VERIFIED — Gemini returned 429 quota exhausted; smoke reported `re-run OCR HTTP 502`, cleanup OK.
- Step 6b live rerun-OCR: NOT VERIFIED — no live Gemini calls run (quota exhausted); covered by mocked tests only.
- Step 7 docs/secret scan: no live Gemini calls; git history contains no real secrets; `tsc` and build exit 0; upload notices added but browser UI NOT VERIFIED.
- End-to-end smoke test: PARTIAL — PDF and handwriting rerun-OCR passed; Batch 2 tutor/notes/quizzes LIVE-VERIFIED; planner PARTIAL; final rerun blocked by Gemini daily quota (20/day).
- Migrations on a blank DB: NOT VERIFIED.
- Tutor live smoke: LIVE-VERIFIED - grounded answer length=187 citations=1; insufficient answer length=73 citations=0; follow-up length=385 citations=1.
- Notes live smoke: LIVE-VERIFIED - four note types HTTP 201, saved/retrievable, raw JSON envelope absent; edit/delete OK.
- Quizzes live smoke: LIVE-VERIFIED - answer keys hidden pre-submit; 100/0 attempts; summary avg=50.0 best=100; short-answer grading correct.
- Planner live smoke: PARTIAL - create/generate/mark/regenerate OK; duplicate pending topics found and fixed; dashboard HTTP 500 in full run, targeted dashboard 200 after; final rerun blocked by quota.
- Batch 2 quota stop: Gemini free tier `gemini-3.6-flash` daily generate-content limit 20/day exhausted; server logged 429 ResourceExhausted; no further live calls attempted.
- Browser UI test: NOT VERIFIED.

Gemini model facts observed live:

- `gemini-2.5-flash` is listed but returns 404 "no longer available to new users".
- `gemini-3.6-flash` passed text and vision.
- `gemini-3.8-flash` and `gemini-3.7-flash` timed out (504, not retried).
- `gemini-embedding-001` gives 768 dims with `output_dimensionality=768`.
- Default `GEMINI_MODEL` is `gemini-3.6-flash`.

The live DB already holds non-test data. Smoke tests may delete only what they create.

### Follow-ups

- Migrate `google.generativeai` to `google.genai`.
- Retry `gemini-3.8-flash` later.
- Remove remaining hardcoded embedding model IDs in tests (`test_jwks.py`, embedding literals in `test_ocr.py`).
- Replace the per-process rate limiter with a shared store for multi-instance use.
- Test migrations on a blank DB.
- Resume-from-failed-page remains open.
- `POST /documents/{id}/retry` resets a failed document to `uploaded` but does not enqueue processing; the processing retry path itself is unit-tested.
- Gemini free tier daily limit for `gemini-3.6-flash` is 20 generate-content requests/day. Wait for reset, then rerun `backend/scripts/smoke_features.py` to verify the planner dashboard and regenerate fix end-to-end.

---

## Decisions

| Decision | Value | Rationale |
|----------|-------|-----------|
| Generative model | `GEMINI_MODEL`, default `gemini-3.6-flash` | Live text and vision passed; `gemini-2.5-flash` unavailable to new users |
| Embedding model | `gemini-embedding-001` | 768 dims with `output_dimensionality=768` |
| pgvector index | HNSW cosine (`b7d41e9a2c63`) | Better recall than IVFFlat for v1 |
| OCR primary | Gemini vision | Best handwriting accuracy |
| OCR fallback | Tesseract (optional) | Printed text only |
| Background jobs | `processing_jobs` + FastAPI `BackgroundTasks` | No Celery/Redis for v1 |
| Auth | Supabase JWT via JWKS | Backend verifies access tokens |
| Storage | Supabase private bucket + signed URLs | Page images are private |
| Quiz grading | Rule-based | MCQ exact match; short answer keyword overlap |
| Quiz answer keys | Stripped from generate/list/get until submit | Prevent pre-submit answer-key leaks |
| Tutor retrieval threshold | `min_similarity` default 0.5 | Live sample query max similarity 0.5607; 0.6 returned no chunks and empty answers |
| Tutor no-evidence path | Non-empty insufficient answer, no fallback citations | Avoid empty assistant messages and misleading citations |
| Planner regenerate | Delete pending/in-progress tasks before inserting replacements | Preserve completed tasks without duplicate pending topics |
| Dev DB | SQLite; Postgres + pgvector for live | Docker not required locally |
| PDF extraction | PyMuPDF (`fitz`) | Verified locally on `samples/sample.pdf` |
| SQLAlchemy | 2.0.55 (pinned) | 2.1.x Cython extensions blocked on this machine |
| pytest-asyncio | 0.23.8, `asyncio_mode = auto` | Async test support on Python 3.13 |
| python-jose | 3.5.0 | `jwk.JWK` removed; use `jwk.construct()` |

---

## Environment template

Copy `backend/.env.example` to `backend/.env` and fill placeholders. Do not commit real values.

```text
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME
DATABASE_URL_SYNC=postgresql://USER:PASSWORD@HOST:5432/DBNAME
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_ANON_KEY=ANON_KEY
SUPABASE_JWKS_URL=https://PROJECT.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_SERVICE_ROLE_KEY=SERVICE_ROLE_KEY
GEMINI_API_KEY=GEMINI_KEY
GEMINI_MODEL=gemini-3.6-flash
GEMINI_TIMEOUT_SECONDS=60
GEMINI_MAX_RETRIES=2
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768
STORAGE_BUCKET=documents
OCR_LIMIT_PAGES_PER_DOC=50
OCR_LIMIT_PAGES_PER_USER_PER_DAY=100
OCR_FALLBACK_ENABLED=false
RATE_LIMIT_UPLOADS_PER_MINUTE=10
RATE_LIMIT_AI_PER_MINUTE=20
RATE_LIMIT_PROCESSING_PER_MINUTE=10
ENVIRONMENT=development
APP_NAME="AI Study Assistant"
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

Frontend (`frontend/.env.local`):

```text
VITE_SUPABASE_URL=https://PROJECT.supabase.co
VITE_SUPABASE_ANON_KEY=ANON_KEY
VITE_API_URL=http://localhost:8000/api
```

---

## Commands

```bash
# Backend
cd backend
venv/Scripts/python.exe -m alembic upgrade head
venv/Scripts/uvicorn.exe app.main:app --reload
venv/Scripts/python.exe -m pytest tests -q

# Frontend
cd frontend
npm install
npm run dev
npm run build
npx tsc -p tsconfig.json --noEmit --incremental false
```

---

## Repo structure

```text
.gitignore
BRIEF.md
PROGRESS.md
README.md
docker-compose.yml
backend/
  .env.example
  alembic.ini
  asa_dev.db
  pytest.ini
  requirements.txt
  alembic/
    README
    env.py
    script.py.mako
    versions/
      159f277202ec_chat_sessions_and_messages.py
      1afc5ac08801_notes_and_quizzes.py
      44187703b244_initial_schema_profiles_subjects.py
      b7d41e9a2c63_add_hnsw_embedding_index.py
      bb319edf69d1_documents_pages_chunks_processing_jobs.py
      e34c954767af_study_plans_and_tasks.py
  app/
    main.py
    ai/ (gemini.py, ocr.py, tesseract.py)
    api/ (chat.py, deps.py, documents.py, health.py, notes.py, pages.py, planner.py, quizzes.py, subjects.py, upload.py)
    core/ (config.py, rate_limit.py, resilience.py)
    db/ (base.py)
    models/ (chat_message.py, chat_session.py, document.py, document_chunk.py, document_page.py, note.py, planner.py, processing_job.py, profile.py, quiz.py, subject.py)
    rag/ (generator.py, retriever.py)
    schemas/ (chat.py, document.py, note.py, planner.py, quiz.py, subject.py)
    services/ (notes.py, planner.py, processing.py, quizzes.py, storage.py)
  scripts/ (smoke_test.py, smoke_features.py)
  tests/ (conftest.py, test_chat.py, test_config.py, test_documents.py, test_isolation.py, test_jwks.py, test_notes_quizzes.py, test_ocr.py, test_planner.py, test_rate_limit.py, test_resilience.py, test_storage_security.py, test_subjects.py)
frontend/
  .env.example
  components.json
  index.html
  package-lock.json
  package.json
  postcss.config.js
  tailwind.config.js
  tsconfig.json
  tsconfig.node.json
  tsconfig.node.tsbuildinfo
  vite.config.d.ts
  vite.config.js
  vite.config.ts
  src/
    App.tsx
    index.css
    main.tsx
    vite-env.d.ts
    components/ui/ (alert-dialog, badge, button, card, dialog, dropdown-menu, form, input, label, navigation-menu, select, separator, sheet, sidebar, skeleton, table, toast, tooltip)
    hooks/ (use-auth.tsx, use-chat.ts, use-documents.ts, use-mobile.ts, use-notes.ts, use-planner.ts, use-quizzes.ts, use-toast.tsx)
    layouts/MainLayout.tsx
    lib/utils.ts
    pages/ (Dashboard, DocumentDetail, Documents, Login, Notes, NotesDetail, PlanDetail, Planner, QuizResults, QuizTake, Quizzes, Register, SubjectDetail, Subjects, Tutor, TutorSession)
    services/ (api.ts, supabase.ts)
    types/index.ts
```
