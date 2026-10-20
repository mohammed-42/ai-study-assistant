# AI Study Assistant — PROGRESS.md

## Current state
- **Phase in progress:** 6 — Planner + Dashboard ✅ COMPLETE
- **Phase status:** Phases 1–6 complete and committed; Phase 7 (Hardening) pending
- **Last updated:** 2026-10-20

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
- ~~**Gemini embeddings and pgvector insertion are placeholders**~~ — `embed_texts()` wired in Phase 3; populates when `GEMINI_API_KEY` is set.
- ~~**OCR has not started**~~ — Completed in Phase 3.
- **Supabase Storage not wired** — upload endpoint accepts files but does not persist to cloud storage (no signed URLs yet). Deferred to Phase 4.

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

### Phase 3 — OCR ✅ DONE
**All items complete. Committed as `feat: Phase 3 — OCR`**.

**Backend (completed):**
- [x] `OcrProvider` interface in `app/ai/ocr.py` (`transcribe_page(image_bytes, mime_type) -> OcrResult`)
- [x] Gemini multimodal vision provider (`app/ai/gemini.py`, model: `gemini-2.0-flash`)
- [x] Optional Tesseract fallback provider (`app/ai/tesseract.py`, printed text only)
- [x] `needs_review` flagging logic: short output (<50 chars), many `[illegible]` markers (>5), low-confidence signals
- [x] Processing pipeline integration: `_process_images` runs OCR on each page image
- [x] Daily OCR limit enforcement (`OCR_LIMIT_PAGES_PER_USER_PER_DAY`)
- [x] Multi-image upload support (`doc_type=multi_image`, 2–20 files, ordered by upload)
- [x] Page edit endpoint: `PUT /api/documents/{doc_id}/pages/{page_id}` with re-embed trigger
- [x] `re_embed_page()` utility: removes old chunks for a page, re-chunks, re-embeds
- [x] Embedding generation stub wired to Gemini (`embed_texts`)

**Frontend (completed):**
- [x] Per-page review/edit UI in `DocumentDetail.tsx` — pencil icon opens inline textarea
- [x] Save/Cancel buttons; on save, calls edit endpoint and invalidates queries
- [x] Badges for OCR source, Needs Review, and Edited states
- [x] `editPage` method added to `documentApi` in `services/api.ts`
- [x] TypeScript types updated (`DocumentChunk.embedding` optional field)

**Tests (completed):**
- [x] `tests/test_ocr.py` — 12 tests, all passing
  - Flagging logic: short text, long clean text, low confidence, many/few illegible markers, custom min_length
  - Gemini provider: API key validation, success case, [NO_TEXT] handling, error fallback
  - Tesseract provider: unavailable fallback, embed NotImplementedError
- [x] All 34 backend tests passing (8 subjects + 14 documents + 12 OCR)
- [x] Frontend TypeScript compiles clean (`tsc --noEmit`)
- [x] Frontend build passes (`npm run build`)

**Known stubs remaining in Phase 3:**
- Supabase Storage file persistence not wired (upload accepts files but doesn't upload to cloud)
- PDF text extraction (`_process_pdf`) still a placeholder (PyMuPDF DLL blocked on this machine)
- Scanned-PDF page rendering at ~200 DPI deferred to later when storage is wired

---

### Phase 4 — Tutor ✅ DONE
**All items complete. Committed as `feat: Phase 4 — Tutor`**.

**Backend (completed):**
- [x] Chat session models: `ChatSession`, `ChatMessage` with proper foreign keys
- [x] Alembic migration: `159f277202ec` (chat_sessions, chat_messages tables)
- [x] RAG retrieval service (`app/rag/retriever.py`): vector search with pgvector, top-k, min similarity threshold, ownership filtering
- [x] Answer generation service (`app/rag/generator.py`): Gemini grounded QA, citation validation, insufficient evidence path
- [x] Chat API endpoints (`app/api/chat.py`):
  - `GET /api/chat/sessions` — list sessions (owner-scoped)
  - `POST /api/chat/sessions` — create session
  - `DELETE /api/chat/sessions/{id}` — delete session with cascading messages
  - `GET /api/chat/sessions/{id}/messages` — list messages
  - `POST /api/chat/sessions/{id}/messages` — send message, get AI response
- [x] Citation validation: verify referenced chunk IDs exist, resolve document name + page
- [x] Insufficient evidence path: explicit "materials don't cover this" message
- [x] Conversation history support for follow-up questions
- [x] Tests: **12 new tests** (all passing)
  - Session CRUD (list, create, delete, ownership isolation)
  - Message listing
  - Retrieval authorization (ownership filter)
  - Citation validation
  - Insufficient evidence path
  - End-to-end answer generation with mocked Gemini

**Frontend (completed):**
- [x] Types: `ChatSession`, `ChatMessage`, `TutorRequest`
- [x] Service: `chatApi` (listSessions, createSession, deleteSession, listMessages, sendMessage)
- [x] Hooks: `useChatSessions`, `useChatMessages`, `useCreateChatSession`, `useDeleteChatSession`, `useSendChatMessage`
- [x] Pages: `Tutor.tsx` (session list with create/delete), `TutorSession.tsx` (chat UI with citation display)
- [x] Routes: `/tutor`, `/tutor/:sessionId` added to `App.tsx`
- [x] Sidebar: Tutor link added to navigation
- [x] TypeScript compiles clean (`tsc --noEmit` passes)
- [x] Frontend build passes (`npm run build`)

**Tests: 46/46 passing** (8 subjects + 14 documents + 12 OCR + 12 chat)

---

### Phase 5 — Notes + Quizzes ✅ DONE
**All items complete. Committed as `feat: Phase 5 — Notes + Quizzes`**.

**Backend (completed):**
- [x] Models: `Note`, `Quiz`, `QuizQuestion`, `QuizAttempt`, `QuizResponse`
- [x] Alembic migration: `1afc5ac08801` (notes, quizzes, quiz_questions, quiz_attempts, quiz_responses tables)
- [x] Notes CRUD API: `GET /api/notes`, `POST /api/notes`, `GET /api/notes/{id}`, `PUT /api/notes/{id}`, `DELETE /api/notes/{id}`
- [x] Notes generate endpoint: `POST /api/notes/generate` with `note_type` param (summary/key_concepts/definitions/revision)
- [x] Notes generation service (`app/services/notes.py`): Gemini-grounded, type-specific prompts, JSON parse + fallback
- [x] Quiz generate endpoint: `POST /api/quizzes/generate` (MCQ + short answer + mixed support)
- [x] Quiz list endpoint: `GET /api/quizzes` (answer keys stripped from list response)
- [x] Quiz get endpoint: `GET /api/quizzes/{id}` (full details incl. answer keys for owner)
- [x] Quiz delete endpoint: `DELETE /api/quizzes/{id}`
- [x] Quiz submit endpoint: `POST /api/quizzes/{id}/submit` — grades MCQ and short answer (rule-based keyword overlap ≥50%)
- [x] Quiz attempts endpoint: `GET /api/quizzes/{id}/attempts`
- [x] Quiz summary endpoint: `GET /api/quizzes/{id}/summary` (total attempts, avg score, best score, recent attempts)
- [x] Quiz generation service (`app/services/quizzes.py`): Gemini prompt-based, Pydantic-validated MCQ schema, answer key protection
- [x] Grading service: MCQ exact-match, short-answer keyword-overlap (≥50% threshold)
- [x] Ownership isolation on all endpoints
- [x] Tests: **16 new tests** (all passing)
  - Notes CRUD (list empty, create, get, update, delete, ownership isolation)
  - Quiz generate (no chunks error, success with mocked Gemini, missing subject/doc validation)
  - Quiz list (empty, ownership isolation)
  - Quiz submit (MCQ correct, MCQ wrong, short answer with keyword overlap)
  - Quiz summary, Quiz delete

**Frontend (completed):**
- [x] Types: `Note`, `NoteCreate`, `Quiz`, `QuizQuestion`, `QuizAttempt`, `QuizResponse`, `QuizSummary`, `QuizGenerateRequest`, `QuizSubmitRequest`
- [x] Service: `noteApi` (list, get, create, update, delete, generate) + `quizApi` (list, get, generate, delete, submit, getAttempts, getSummary)
- [x] Hooks: `useNotes`, `useNote`, `useCreateNote`, `useUpdateNote`, `useDeleteNote`, `useGenerateNote`, `useQuizzes`, `useQuiz`, `useQuizAttempts`, `useQuizSummary`, `useGenerateQuiz`, `useSubmitQuiz`, `useDeleteQuiz`
- [x] Pages: `Notes.tsx` (list + generate dialog), `NotesDetail.tsx` (view/edit), `Quizzes.tsx` (list + generate + delete), `QuizTake.tsx` (take quiz with MCQ/radio + short answer/textarea + submit + results), `QuizResults.tsx` (score summary + per-question breakdown + attempt history)
- [x] Routes: `/notes`, `/notes/:id`, `/quizzes`, `/quizzes/:id`, `/quizzes/:id/results` added to `App.tsx`
- [x] Sidebar: Notes and Quizzes links added
- [x] TypeScript compiles clean (`tsc --noEmit` passes)
- [x] Frontend build passes (`npm run build`)

**Tests: 62/62 passing** (8 subjects + 14 documents + 12 OCR + 12 chat + 16 notes+quizzes)

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
        __init__.py            # Exports: Profile, Subject, Document, DocumentPage, DocumentChunk, ProcessingJob, ChatSession, ChatMessage
        profile.py             # profiles table
        subject.py             # subjects table
        document.py            # documents table
        document_page.py       # document_pages table
        document_chunk.py      # document_chunks table (with pgvector Vector column)
        processing_job.py      # processing_jobs table
        chat_session.py        # chat_sessions table
        chat_message.py        # chat_messages table
      schemas/
        subject.py             # SubjectCreate, SubjectOut, SubjectUpdate
        document.py            # DocumentOut, DocumentPageOut, DocumentChunkOut
        chat.py                # ChatSessionOut, ChatMessageOut, MessageCreate
      api/
        __init__.py            # health_router, subjects_router, documents_router, upload_router, pages_router, chat_router
        deps.py                # get_current_user (Supabase JWT verify via JWKS)
        health.py              # GET /api/health
        subjects.py            # CRUD /api/subjects (owner-scoped)
        documents.py           # GET/DELETE/retry documents, pages, chunks
        upload.py              # POST /api/documents/upload (file validation)
        chat.py                # Chat sessions and messages CRUD
      rag/
        __init__.py            # RAG service exports
        retriever.py           # Vector search with pgvector, ownership filtering
        generator.py           # Gemini grounded QA with citation validation
      services/
        processing.py          # Chunking logic (tested), processing pipeline stub (PyMuPDF lazy, embedding placeholder)
      tests/
        conftest.py            # in-memory SQLite fixtures, env overrides
        test_subjects.py       # 8 tests, all passing
        test_documents.py      # 14 tests, all passing
        test_ocr.py            # 12 tests, all passing
        test_chat.py           # 12 tests, all passing
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
        use-chat.ts            # useChatSessions, useChatMessages, useCreateChatSession, useDeleteChatSession, useSendChatMessage
      layouts/MainLayout.tsx   # Sidebar + header + Outlet
      pages/
        Login.tsx
        Register.tsx
        Dashboard.tsx          # subject cards, empty state
        Subjects.tsx           # list/create/delete with mutations
        SubjectDetail.tsx
        Documents.tsx          # document list table with status badges
        DocumentDetail.tsx     # pages and chunks display
        Tutor.tsx              # Chat session list page
        TutorSession.tsx       # Chat UI with message display and citation badges
      services/
        supabase.ts            # createSupabaseClient
        api.ts                 # apiFetch wrapper + documentApi + chatApi
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

7. ~~**Embeddings are placeholder zeros**~~ — Gemini `embed_texts()` wired; embeddings populate when Gemini API key is configured. (Still zeros in tests where no API key is set.)

8. ~~**OCR not started**~~ — Phase 3 complete: `OcrProvider` interface, Gemini vision provider, Tesseract fallback, page edit UI, re-embed pipeline all implemented.

---

## Commits

- `feat: Phase 1 — Foundation complete` (1d9dcc0) — repo scaffold, docker-compose, config validation, models + Alembic migration, health check, Supabase Auth token verification middleware, subjects CRUD (backend + frontend), protected routing, dashboard shell, 8 backend tests passing, frontend build clean.
- `feat: Phase 2 — Documents` (6e8db95) — backend models (Document, DocumentPage, DocumentChunk, ProcessingJob), Alembic migration bb319edf69d1, upload endpoint with validation, CRUD API, processing stub, 14 document tests passing.
- `feat: Phase 2 frontend documents pages` (09c7b3b) — frontend Document types, documentApi service, useDocuments hook, Documents list page, DocumentDetail page, routes, badge component.
- `docs: update PROGRESS.md — Phase 2 fully complete with frontend` (8714e66)
- `feat: Phase 3 — OCR` — OcrProvider interface, Gemini vision provider, Tesseract fallback, needs_review flagging, multi-image upload, page edit/re-embed API, per-page review UI, 12 OCR tests + 34 total backend tests passing, frontend build clean.
- `feat: Phase 4 — Tutor` — RAG retrieval service, Gemini grounded QA with citation validation, chat sessions/messages API, frontend tutor pages with chat UI, 12 new tests, 46 total backend tests passing, frontend build clean.
- `feat: Phase 5 — Notes + Quizzes` — Note/Quiz models + Alembic migration, Gemini-grounded notes generation (4 types), quiz generation (MCQ + short answer + mixed), rule-based grading, full CRUD + submit + attempts + summary APIs, frontend Notes/Quizzes pages with generate dialogs and quiz-take UI, 16 new tests, 62 total backend tests passing, frontend build clean.
- `fix: Phase 6 planner tests — cascade delete + subject_id constraint` (36d7afa) — explicit task cascade in delete_plan endpoint, fix test_document_counts_subject_id constraint, pin SQLAlchemy 2.0.55 (Windows DLL block on 2.1.x Cython). 81/81 tests passing.
- `docs: update PROGRESS.md — Phase 6 complete, 81/81 tests passing` — progress.md updated with Phase 6 full details.


ke UI, 16 new tests, 62 total backend tests passing, frontend build clean.                                                                    
### Phase 6 — Planner + Dashboard ✅ COMPLETE
**All items complete. Committed as `fix: Phase 6 planner tests — cascade delete + subject_id constraint` (36d7afa).**

**Backend (completed):**
- [x] Models: `StudyPlan`, `StudyTask` in `app/models/planner.py`
- [x] Alembic migration: `e34c954767af` (study_plans, study_tasks tables)
- [x] Rule-based scheduler service (`app/services/planner.py`): `generate_schedule()`, `regenerate_plan()` — respects daily minutes, preferred days, importance scoring, quiz performance
- [x] API endpoints (`app/api/planner.py`):
  - `GET /api/planner/plans` — list (owner-scoped)
  - `POST /api/planner/plans` — create
  - `GET /api/planner/plans/{id}` — get with tasks
  - `PUT /api/planner/plans/{id}` — update (title, exam_date, daily_minutes, preferred_days, topics, status)
  - `DELETE /api/planner/plans/{id}` — delete (cascade: explicit task deletion for SQLite compat)
  - `POST /api/planner/plans/{id}/generate` — generate schedule from topics
  - `POST /api/planner/plans/{id}/regenerate` — regenerate (preserves completed tasks)
  - `PUT /api/planner/tasks/{id}` — update task status/actual_minutes
  - `DELETE /api/planner/tasks/{id}` — delete task
  - `GET /api/planner/dashboard` — computed stats (doc counts, active plans, today's tasks, plan progress, weak topics)
- [x] Ownership isolation on all endpoints
- [x] Import path fixes applied: `app.models.study_plan` → `app.models.planner`, `app.models.quiz_attempt` → `app.models.quiz`
- [x] `db.func` → `func` import fix in planner.py
- [x] SQLAlchemy downgraded to 2.0.55 (Windows DLL block on 2.1.x Cython extensions)

**Frontend (completed):**
- [x] Types: `StudyPlan`, `StudyPlanCreate`, `StudyPlanUpdate`, `StudyTask`, `StudyTaskUpdate`, `DashboardData` in `types/index.ts`
- [x] Service: `plannerApi` in `services/api.ts` (listPlans, getPlan, createPlan, updatePlan, deletePlan, generateSchedule, regenerateSchedule, updateTask, deleteTask, getDashboard)
- [x] Hooks: `use-planner.ts` — usePlannerPlans, usePlannerPlan, useCreatePlan, useUpdatePlan, useDeletePlan, useGenerateSchedule, useRegenerateSchedule, useUpdateTask, useDashboard
- [x] Pages: `Planner.tsx` (plan list + create dialog), `PlanDetail.tsx` (plan view + task management + generate/regenerate)
- [x] Routes: `/planner`, `/planner/:id` added to `App.tsx`
- [x] Sidebar: Planner link added
- [x] Dashboard updated: real stats cards (documents, plans, today's tasks, plan progress %)
- [x] TypeScript compiles clean (`tsc --noEmit` passes)
- [x] Frontend build passes (`npm run build`)

**Tests (completed):**
- [x] `tests/test_planner.py` — 19 tests, all passing
  - Plan CRUD (create, list, get, update, delete)
  - Ownership isolation
  - Schedule generation (creates tasks, rejects past exam)
  - Task updates and deletion
  - Cascade delete (explicit task deletion for SQLite compat)
  - Dashboard stats (returns stats, document counts with valid subject_id)

**Tests: 81/81 passing** (8 subjects + 14 documents + 12 OCR + 12 chat + 16 notes+quizzes + 19 planner)

**Bugs fixed mid-stream:**
- `planner.py` syntax error: `un scheduled_topics` → `unscheduled_topics` (services/planner.py line 85)
- `planner.py` double-dot: `..scalars().all()` → `.scalars().all()` (api/planner.py line 304)
- Wrong imports: `study_plan`, `study_task`, `quiz_attempt` → `planner`, `quiz`
- `regenerate_schedule` endpoint had `Depends(get_current_user)` for `db` param → fixed to `Depends(get_db)`
- Quiz join referenced `StudyPlan` instead of `Quiz` model
- Dashboard used `db.func` (AsyncSession has no `func`) → replaced with `sqlalchemy.func`
- Frontend: removed unused `plannerApi` import in Planner.tsx, removed unused `StudyPlan` type import
- **Cascade delete**: SQLite ORM doesn't enforce FK CASCADE → explicit `DELETE FROM study_tasks WHERE plan_id = ?` before plan delete
- **Test data**: `Document.subject_id` NOT NULL → test now creates a subject first

### Phase 6 — Planner + Dashboard ✅ BACKEND + FRONTEND COMPLETE (tests in progress)
**Backend (completed):**
- [x] Models: `StudyPlan`, `StudyTask` in `app/models/planner.py`
- [x] Alembic migration: `e34c954767af` (study_plans, study_tasks tables)
- [x] Rule-based scheduler service (`app/services/planner.py`): `generate_schedule()`, `regenerate_plan()` — respects daily minutes, preferred days, importance scoring, quiz performance
- [x] API endpoints (`app/api/planner.py`):
  - `GET /api/planner/plans` — list (owner-scoped)
  - `POST /api/planner/plans` — create
  - `GET /api/planner/plans/{id}` — get with tasks
  - `PUT /api/planner/plans/{id}` — update (title, exam_date, daily_minutes, preferred_days, topics, status)
  - `DELETE /api/planner/plans/{id}` — delete (cascade)
  - `POST /api/planner/plans/{id}/generate` — generate schedule from topics
  - `POST /api/planner/plans/{id}/regenerate` — regenerate (preserves completed tasks)
  - `PUT /api/planner/tasks/{id}` — update task status/actual_minutes
  - `DELETE /api/planner/tasks/{id}` — delete task
  - `GET /api/planner/dashboard` — computed stats (doc counts, active plans, today's tasks, plan progress, weak topics)
- [x] Ownership isolation on all endpoints
- [x] Import path fixes applied: `app.models.study_plan` → `app.models.planner`, `app.models.quiz_attempt` → `app.models.quiz`
- [x] `db.func` → `func` import fix in planner.py

**Frontend (completed):**
- [x] Types: `StudyPlan`, `StudyPlanCreate`, `StudyPlanUpdate`, `StudyTask`, `StudyTaskUpdate`, `DashboardData` in `types/index.ts`
- [x] Service: `plannerApi` in `services/api.ts` (listPlans, getPlan, createPlan, updatePlan, deletePlan, generateSchedule, regenerateSchedule, updateTask, deleteTask, getDashboard)
- [x] Hooks: `use-planner.ts` — usePlannerPlans, usePlannerPlan, useCreatePlan, useUpdatePlan, useDeletePlan, useGenerateSchedule, useRegenerateSchedule, useUpdateTask, useDashboard
- [x] Pages: `Planner.tsx` (plan list + create dialog), `PlanDetail.tsx` (plan view + task management + generate/regenerate)
- [x] Routes: `/planner`, `/planner/:id` added to `App.tsx`
- [x] Sidebar: Planner link added
- [x] Dashboard updated: real stats cards (documents, plans, today's tasks, plan progress %)
- [x] TypeScript compiles clean (`tsc --noEmit` passes)
- [x] Frontend build passes (`npm run build`)

**Tests (in progress — writing):**
- [x] `tests/test_planner.py` created with 19 test cases covering:
  - Plan CRUD (create, list, get, update, delete)
  - Ownership isolation
  - Schedule generation (creates tasks, rejects past exam)
  - Task updates and deletion
  - Dashboard stats
- [ ] Fix remaining test failures (cascade delete SQL, Document subject_id NOT NULL constraint) before final commit
- [ ] Expected: 62 + 19 = 81 total backend tests passing once cascade issue resolved

**Bugs fixed mid-stream:**
- `planner.py` syntax error: `un scheduled_topics` → `unscheduled_topics` (services/planner.py line 85)
- `planner.py` double-dot: `..scalars().all()` → `.scalars().all()` (api/planner.py line 304)
- Wrong imports: `study_plan`, `study_task`, `quiz_attempt` → `planner`, `quiz`
- `regenerate_schedule` endpoint had `Depends(get_current_user)` for `db` param → fixed to `Depends(get_db)`
- Quiz join referenced `StudyPlan` instead of `Quiz` model
- Dashboard used `db.func` (AsyncSession has no `func`) → replaced with `sqlalchemy.func`
- Frontend: removed unused `plannerApi` import in Planner.tsx, removed unused `StudyPlan` type import

**Known issues:**
- SQLite CASCADE delete not enforced — `test_delete_plan_cascades_tasks` fails because SQLAlchemy `DELETE` on plan doesn't remove orphaned tasks in SQLite without explicit cascade handling in the session
- `Document.subject_id` is required (NOT NULL) — `test_dashboard_counts_documents` fails because test creates a Document without a subject_id
- These are test-data issues, not production bugs