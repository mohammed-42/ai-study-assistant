# AI Study Assistant — PROGRESS.md

## Current state
- **Phase in progress:** 3 — OCR (NOT STARTED; begin only on explicit instruction)
- **Phase status:** Phase 1 and Phase 2 complete and committed; Phase 3 pending
- **Last updated:** 2026-10-15

---

## Phase checklist

### Phase 1 — Foundation ✅ DONE (1 commit)
**All items complete. Committed as `feat: Phase 1 — Foundation complete` (1d9dcc0).**

- [x] Repo initialized, .gitignore, README stub
- [x] `docker-compose.yml` (Postgres + pgvector)
- [x] Backend scaffold (FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic)
- [x] Config validation (env vars, clear startup errors)
- [x] Database models + Alembic migration (clean apply on SQLite for dev; PG migration generated)
- [x] Health check endpoint
- [x] Supabase token verification middleware on backend
- [x] Subjects CRUD API (full: list/create/get/update/delete + ownership isolation)
- [x] Backend tests — **8/8 passing** (health, list, create, get, update, delete, ownership isolation, unauthenticated reject)
- [x] Frontend scaffold (Vite + React + TS + Tailwind 3.x + shadcn/ui)
- [x] shadcn/ui components installed (button, input, label, card, dialog, form, sidebar, toast, table, skeleton, etc.)
- [x] TanStack Query + React Hook Form + Zod configured
- [x] Supabase client on frontend
- [x] Register / Login screens (React Router protected)
- [x] Dashboard shell with empty state
- [x] Subjects page with create/delete UI
- [x] Subject detail page
- [x] MainLayout with sidebar navigation
- [x] TypeScript compiles clean (`tsc --noEmit` passes)
- [x] Frontend build passes (`npm run build` clean)
- [x] First git commit: `feat: Phase 1 — Foundation complete`

### Phase 2 — Documents ✅ DONE (3 commits)
**All items complete. Committed across:**
- `feat: Phase 2 — Documents` (6e8db95) — backend models, migration, API, processing stub, tests
- `feat: Phase 2 frontend documents pages` (09c7b3b) — frontend types, services, hooks, pages, routes
- `docs: update PROGRESS.md — Phase 2 fully complete with frontend` (8714e66)

**Backend (completed):**
- [x] Models: `Document`, `DocumentPage`, `DocumentChunk`, `ProcessingJob`
- [x] Alembic migration: `bb319edf69d1` (documents, document_pages, document_chunks, processing_jobs tables)
- [x] Upload endpoint: `POST /api/documents/upload` with PDF magic-bytes validation and Pillow image decode
- [x] Document CRUD: `GET /api/documents/`, `GET /api/documents/{id}`, `DELETE /api/documents/{id}`, `POST /api/documents/{id}/retry`
- [x] Pages/chunks endpoints: `GET /api/documents/{id}/pages`, `GET /api/documents/{id}/chunks`
- [x] Chunking logic: token-aware (~800 tokens, ~120 overlap, page_start/page_end) — tested standalone
- [x] Status transitions: `uploaded → processing → ready | failed`
- [x] Delete cascades: chunks → pages → document record
- [x] Tests: **14 passing** (upload validation, CRUD, ownership isolation, unauthenticated reject, chunking logic, pipeline stub)
- [x] Processing service stub: `app/services/processing.py` (PyMuPDF lazy-loaded; Gemini embedding placeholder)

**Known stubs and limitations in Phase 2:**
- **PyMuPDF text extraction is deferred/limited** — DLL load blocked by Windows Application Control policy on this machine; `fitz` is imported lazily and will fail at runtime if a real PDF is processed. The chunking logic itself (pure Python) is tested and works.
- **Gemini embeddings and pgvector insertion are placeholders** — `embedding` column stores zeros until the Gemini SDK is wired up in Phase 3 or later.
- **OCR has not started** — no `OcrProvider` interface or Gemini vision integration exists yet.
- **Supabase Storage not wired** — upload endpoint accepts files but does not persist to cloud storage (no signed URLs yet).

**Frontend (completed):**
- [x] Types: `AppDocument`, `DocumentPage`, `DocumentChunk`, `DocumentStatus`
- [x] Service: `documentApi` (list, get, delete, retry, upload, getPages, getChunks)
- [x] Hooks: `useDocuments`, `useDeleteDocument`, `useRetryDocument`, `useUploadDocument`
- [x] Pages: `Documents.tsx` (list with table, status badges), `DocumentDetail.tsx` (pages/chunks display)
- [x] Routes: `/documents`, `/documents/:id` added to `App.tsx`
- [x] shadcn/ui badge component added
- [x] TypeScript compiles clean, `npm run build` passes

**Backend tests: 22/22 passing** (8 subjects + 14 documents)

---

### Phase 3 — OCR (NOT STARTED)
Begin only on explicit user instruction.

Planned:
- [ ] `OcrProvider` interface (`transcribe_page(image_bytes) -> text + flags`)
- [ ] Gemini multimodal vision primary provider (`gemini-2.0-flash`)
- [ ] Optional Tesseract fallback for printed text only
- [ ] Per-page review/edit UI with re-embedding on edit
- [ ] OCR limits (pages per doc, pages per user per day)
- [ ] `needs_review` flagging logic
- [ ] Multi-image upload as single document (ordered pages)
- [ ] Scanned-PDF page rendering at ~200 DPI
- [ ] Tests for OCR path selection, response handling, flagging

---

## Decisions (Section 2 — Tech Stack)

| Decision | Value | Rationale |
|----------|-------|-----------|
| Embedding model | `text-embedding-004` | Current Gemini stable embedding; 768-dim output |
| pgvector column dim | 768 | Matches `text-embedding-004`; configurable via `EMBEDDING_DIM` env var |
| pgvector index | IVFFlat (lists=100) | Simpler to set up than HNSW; sufficient for v1; can upgrade to HNSW later |
| OCR primary provider | Gemini multimodal vision (`gemini-2.0-flash`) | Best handwriting accuracy vs Tesseract fallback |
| OCR fallback | Tesseract (optional, printed text only) | Configurable via `OCR_FALLBACK_ENABLED=true` |
| Background jobs | `processing_jobs` table + FastAPI `BackgroundTasks` + startup sweep | No Celery/Redis for v1; justified simplicity per brief |
| Auth | Supabase Auth (JWT) | Backend verifies access token via JWKS; Supabase URL + anon key exposed only to frontend |
| Storage | Supabase private bucket | Signed URLs for page images |
| Quiz short-answer grading | Rule-based self-check against stored model answer (no AI grading in v1) | Per brief scope |
| Topics | Plain `topic` string in `study_tasks` (no separate topics table for v1) | Simpler; hierarchy out of scope |
| RLS | Enabled on auth tables; backend ownership checks remain primary control | Defense in depth |
| Dev DB | SQLite (aiosqlite) for local dev | Docker not available on this machine; migrations generated against Postgres schema |
| pytest-asyncio | 0.23.8 with `asyncio_mode = auto` in `pytest.ini` | Cleanest async test support on Python 3.13 |
| shadcn version | `npx shadcn@latest` (v4.21) | Current recommended CLI; deprecated `shadcn-ui` avoided |
| PyMuPDF import | Lazy (deferred) | Windows DLL policy blocks import at module load time; chunking logic tested standalone without it |

---

## Environment variables required

**Backend** (copy `.env.example` → `.env`, fill real values):
```
DATABASE_URL=postgresql+asyncpg://asa_user:asa_pass@localhost:5432/ai_study_assistant
DATABASE_URL_SYNC=postgresql://asa_user:asa_pass@localhost:5432/ai_study_assistant
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWKS_URL=https://api.supabase.com/auth/v1/keys
GEMINI_API_KEY=your-gemini-api-key
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIM=768
STORAGE_BUCKET=documents
OCR_LIMIT_PAGES_PER_DOC=50
OCR_LIMIT_PAGES_PER_USER_PER_DAY=100
OCR_FALLBACK_ENABLED=false
APP_NAME="AI Study Assistant"
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Frontend** (copy `.env.example` → `.env.local`):
```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000/api
```

---

## Commands

```bash
# Dev DB (if Docker available)
docker compose up -d

# Backend
cd backend
venv/Scripts/pip.exe install -r requirements.txt
venv/Scripts/python.exe -m alembic upgrade head   # applies migration
venv/Scripts/uvicorn.exe app.main:app --reload    # dev server at :8000
venv/Scripts/python.exe -m pytest tests/ -v       # run tests

# Frontend
cd frontend
npm install
npm run dev        # dev server at :5173
npm run build      # production build
npx tsc --noEmit   # type-check only
```

---

## Repo structure (current)

```
ai-study-assistant/
  BRIEF.md
  PROGRESS.md
  docker-compose.yml
  .gitignore
  backend/
    app/
      main.py                  # FastAPI app, CORS, routers, startup
      core/config.py           # Settings (lazy-loaded, env-overridable)
      db/base.py               # Base, get_db, init_db, reset_db_for_testing
      models/
        __init__.py            # Exports: Profile, Subject, Document, DocumentPage, DocumentChunk, ProcessingJob
        profile.py             # profiles table
        subject.py             # subjects table
        document.py            # documents table
        document_page.py       # document_pages table
        document_chunk.py      # document_chunks table (with pgvector Vector column)
        processing_job.py      # processing_jobs table
      schemas/
        subject.py             # SubjectCreate, SubjectOut, SubjectUpdate
        document.py            # DocumentOut, DocumentPageOut, DocumentChunkOut
      api/
        __init__.py            # health_router, subjects_router, documents_router, upload_router
        deps.py                # get_current_user (Supabase JWT verify via JWKS)
        health.py              # GET /api/health
        subjects.py            # CRUD /api/subjects (owner-scoped)
        documents.py           # GET/DELETE/retry documents, pages, chunks
        upload.py              # POST /api/documents/upload (file validation)
      services/
        processing.py          # Chunking logic (tested), processing pipeline stub (PyMuPDF lazy, embedding placeholder)
      tests/
        conftest.py            # in-memory SQLite fixtures, env overrides
        test_subjects.py       # 8 tests, all passing
        test_documents.py      # 14 tests, all passing
    alembic/
      env.py                   # Sync engine for migrations
      ini                      # points at SQLite for dev
      versions/
        44187703b244_initial_schema_profiles_subjects.py
        bb319edf69d1_documents_pages_chunks_processing_jobs.py
    .env                       # local dev (SQLite)
    .env.example
    requirements.txt
    pytest.ini
  frontend/
    src/
      App.tsx                  # Router: /login, /register, / (protected), /subjects, /subjects/:id, /documents, /documents/:id
      main.tsx
      index.css                # Tailwind + shadcn CSS vars
      types/index.ts           # Subject, UserProfile, AppDocument, DocumentPage, DocumentChunk, Database
      hooks/
        use-auth.tsx           # AuthContext (Supabase client)
        use-toast.tsx          # Toast hook + Toaster component
        use-documents.ts       # useDocuments, useDeleteDocument, useRetryDocument, useUploadDocument
      layouts/MainLayout.tsx   # Sidebar + header + Outlet
      pages/
        Login.tsx
        Register.tsx
        Dashboard.tsx          # subject cards, empty state
        Subjects.tsx           # list/create/delete with mutations
        SubjectDetail.tsx
        Documents.tsx          # document list table with status badges
        DocumentDetail.tsx     # pages and chunks display
      services/
        supabase.ts            # createSupabaseClient
        api.ts                 # apiFetch wrapper + documentApi (list/get/upload/delete/retry/pages/chunks)
      components/ui/           # shadcn components (17 components including badge)
    package.json
    vite.config.ts
    tailwind.config.js
    postcss.config.js
    tsconfig.json
    .env.example
```

---

## Known issues

1. ~~**Frontend build blocked**~~ — **FIXED.** Added `resolve.alias` in `vite.config.ts` with `@types/node`. Build and `tsc --noEmit` both pass.

2. **Docker unavailable** on this machine — dev DB defaults to SQLite in-memory for tests, file-based SQLite for live dev. Migration SQL generated correctly for Postgres+pgvector; will need Postgres running for production integration.

3. **No live smoke test possible** — requires real Supabase project + Gemini API key. Script documented in README once Phase 1 complete.

4. **Pydantic v2 `ConfigDict` migration** — `app/core/config.py` uses deprecated class-based `config`. Cosmetic; does not affect functionality.

5. **FastAPI `on_event` deprecation** — `main.py` uses `@app.on_event("startup")`. Works but should migrate to `lifespan` handler before hardening phase.

6. **PyMuPDF DLL blocked on Windows** — Application Control policy prevents loading `_mupdf.dll`. `fitz` is imported lazily in `processing.py`; chunking logic (pure Python) is tested and works. Real PDF text extraction will fail until this is resolved or a workaround is applied.

7. **Embeddings are placeholder zeros** — `document_chunks.embedding` stores `[0.0] * 768` until Gemini SDK is integrated. Vector search is non-functional until Phase 3+ OCR and embedding wiring is complete.

8. **OCR not started** — no `OcrProvider` interface or Gemini vision integration exists yet. Phase 3 pending.

---

## Commits

- `feat: Phase 1 — Foundation complete` (1d9dcc0) — repo scaffold, docker-compose, config validation, models + Alembic migration, health check, Supabase Auth token verification middleware, subjects CRUD (backend + frontend), protected routing, dashboard shell, 8 backend tests passing, frontend build clean.
- `feat: Phase 2 — Documents` (6e8db95) — backend models (Document, DocumentPage, DocumentChunk, ProcessingJob), Alembic migration bb319edf69d1, upload endpoint with validation, CRUD API, processing stub, 14 document tests passing.
- `feat: Phase 2 frontend documents pages` (09c7b3b) — frontend Document types, documentApi service, useDocuments hook, Documents list page, DocumentDetail page, routes, badge component.
- `docs: update PROGRESS.md — Phase 2 fully complete with frontend` (8714e66)

---

## Phase 3 — OCR (pending explicit instruction)

Todo for Phase 3:
- [ ] `OcrProvider` interface with `transcribe_page(image_bytes) -> text + flags`
- [ ] Gemini multimodal vision provider (`gemini-2.0-flash`)
- [ ] Optional Tesseract fallback for printed text only
- [ ] Per-page review/edit UI with re-embedding on edit
- [ ] OCR limits (pages per doc, pages per user per day)
- [ ] `needs_review` flagging logic (short output, `[illegible]` markers, low-quality signal)
- [ ] Multi-image upload as single document (ordered pages)
- [ ] Scanned-PDF page rendering at ~200 DPI
- [ ] Tests: OCR path selection, prompt/response handling, flagging, resume-from-failed-page
- [ ] Update README with OCR accuracy disclaimer and privacy notice
- [ ] Update PROGRESS.md, commit
