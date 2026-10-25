# AI Study Assistant — PROGRESS

## Current state

- **Phase:** 7 — Hardening. Code complete; live verification in progress.
- **Backend tests:** 112/112 passing (mocked/hermetic).
- **Frontend:** `tsc --noEmit` and `npm run build` clean.
- **Last updated:** 2026-10-25

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
| 7 | Hardening: rate limits, signed URLs, storage cleanup, resilience, docs | Code complete; live verification in progress |

OCR uses Gemini vision through `settings.GEMINI_MODEL` (default `gemini-3.6-flash`).

---

## Phase 7 — Hardening

| Item | Status | Evidence |
|------|--------|----------|
| Backend suite | UNIT-TESTED (mocked) | `pytest -q` → 112 passed |
| Frontend typecheck + build | UNIT-TESTED (mocked) | `tsc` exit 0; `npm run build` exit 0 |
| Rate limits (upload, AI, re-embed) | UNIT-TESTED (mocked) | `tests/test_rate_limit.py`; process-local |
| Signed page-image URLs | UNIT-TESTED (mocked) | `tests/test_storage_security.py` |
| Storage upload/delete wiring | UNIT-TESTED (mocked) | storage tests; live storage path not exercised |
| PDF text extraction (PyMuPDF) | LIVE-VERIFIED | fitz 1.28.2 opened `samples/sample.pdf`: 3 pages, chars `[1935, 2198, 1205]` |
| DB pooler | LIVE-VERIFIED | Connection succeeded; issue RESOLVED (wrong pooler host prefix and a password with special characters) |
| Alembic upgrade + HNSW index | LIVE-VERIFIED | Stamped and upgraded to `b7d41e9a2c63`; HNSW index present |
| FK cascades | LIVE-VERIFIED | Cascade deletes confirmed against live DB |
| JWKS | LIVE-VERIFIED | Key fetched from configured JWKS endpoint |
| Gemini text, vision, embedding | LIVE-VERIFIED | Text and vision passed; `gemini-embedding-001` returned 768 dims with `output_dimensionality=768` |
| Supabase login | LIVE-VERIFIED | Login succeeded |
| End-to-end smoke test | NOT VERIFIED | First attempt timed out on `GET /api/subjects/` |
| Migrations on a blank DB | NOT VERIFIED | — |
| Tutor, notes, quizzes, planner against real Gemini | NOT VERIFIED | — |
| Browser UI test | NOT VERIFIED | — |

### Live verification log

- DB connection: LIVE-VERIFIED. Pooler issue RESOLVED — cause was a wrong pooler host prefix and a password with special characters.
- Alembic stamped and upgraded to `b7d41e9a2c63`; HNSW index LIVE-VERIFIED.
- FK cascades: LIVE-VERIFIED.
- JWKS key: LIVE-VERIFIED.
- Gemini text, vision and 768-dim embedding: LIVE-VERIFIED.
- Supabase login: LIVE-VERIFIED.
- End-to-end smoke test: NOT VERIFIED — first attempt timed out on `GET /api/subjects/`.
- Migrations on a blank DB: NOT VERIFIED.
- Tutor, notes, quizzes and planner against real Gemini: NOT VERIFIED.
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
- Remove hardcoded model IDs in `app/ai/gemini.py` and tests.
- Replace Tailwind v4 syntax in shadcn components.
- Replace the per-process rate limiter with a shared store for multi-instance use.
- Test migrations on a blank DB.
- Scanned-PDF rendering, per-document OCR cap, resume-from-failed-page and re-run-OCR are NOT VERIFIED.

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
  scripts/ (smoke_test.py)
  tests/ (conftest.py, test_chat.py, test_config.py, test_documents.py, test_jwks.py, test_notes_quizzes.py, test_ocr.py, test_planner.py, test_rate_limit.py, test_resilience.py, test_storage_security.py, test_subjects.py)
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
