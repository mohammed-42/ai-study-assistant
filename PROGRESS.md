# AI Study Assistant — PROGRESS.md

## Current state
- **Phase in progress:** 1 — Foundation (COMMITTED)
- **Phase status:** Phase 1 fully complete and committed; no additional work started since last session
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

### Phase 2 — Documents (NOT STARTED — 0% complete)

- [ ] Add `documents`, `document_pages`, `document_chunks`, `processing_jobs` models + Alembic migration
- [ ] Supabase Storage bucket setup docs (signed URLs for upload/download)
- [ ] File upload endpoint with validation (PDF magic bytes, image decode via Pillow, size/page/dimension limits)
- [ ] Multi-image upload as single document (ordered pages)
- [ ] `processing_jobs` table + background task dispatch
- [ ] PyMuPDF text extraction (text-layer pages)
- [ ] Chunking logic (token-aware, ~800 tokens, ~120 overlap, page_start/page_end)
- [ ] Embedding call + pgvector insert (idempotent — no duplicate chunks)
- [ ] Document status transitions: `uploaded → processing → ready | failed`
- [ ] Delete endpoint (storage object + chunks + embeddings + metadata, tolerate partial failure)
- [ ] Frontend: documents list page (paginated, filter by subject), document detail, status display, retry failed
- [ ] Tests: upload validation, chunking, idempotent re-run, deletion cleanup
- [ ] Update PROGRESS.md, commit

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

## Repo structure built

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
      models/profile.py        # profiles table
      models/subject.py        # subjects table
      schemas/subject.py       # SubjectCreate, SubjectOut, SubjectUpdate
      api/
        deps.py                # get_current_user (Supabase JWT verify via JWKS)
        health.py              # GET /api/health
        subjects.py            # CRUD /api/subjects (owner-scoped)
      tests/
        conftest.py            # in-memory SQLite fixtures, env overrides
        test_subjects.py       # 8 tests, all passing
    alembic/
      env.py                   # Sync engine for migrations
      ini                      # points at SQLite for dev
      versions/
        44187703b244_initial_schema_profiles_subjects.py
    .env                       # local dev (SQLite)
    .env.example
    requirements.txt
    pytest.ini
  frontend/
    src/
      App.tsx                  # Router: /login, /register, / (protected), /subjects, /subjects/:id
      main.tsx
      index.css                # Tailwind + shadcn CSS vars
      types/index.ts           # Subject, UserProfile, Database
      hooks/
        use-auth.tsx           # AuthContext (Supabase client)
        use-toast.tsx          # Toast hook + Toaster component
      layouts/MainLayout.tsx   # Sidebar + header + Outlet
      pages/
        Login.tsx
        Register.tsx
        Dashboard.tsx          # subject cards, empty state
        Subjects.tsx           # list/create/delete with mutations
        SubjectDetail.tsx
      services/
        supabase.ts            # createSupabaseClient
        api.ts                 # apiFetch wrapper (Bearer token from localStorage)
      components/ui/           # shadcn components (16 components)
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

4. **Pydantic v2 `ConfigDict` migration** — `app/core/config.py` uses deprecated class-based `config`. Cosmetic; does not affect functionality. Will fix before Phase 2 starts.

5. **FastAPI `on_event` deprecation** — `main.py` uses `@app.on_event("startup")`. Works but should migrate to `lifespan` handler before Phase 2 to keep code clean.

---

## Commits

- `feat: Phase 1 — Foundation complete` (1d9dcc0) — repo scaffold, docker-compose, config validation, models + Alembic migration, health check, Supabase Auth token verification middleware, subjects CRUD (backend + frontend), protected routing, dashboard shell, 8 backend tests passing, frontend build clean.

---

## Phase 2 — Documents (next)

Todo for Phase 2:
- [ ] Add `documents`, `document_pages`, `document_chunks`, `processing_jobs` models + Alembic migration
- [ ] Supabase Storage bucket setup docs (signed URLs for upload/download)
- [ ] File upload endpoint with validation (PDF magic bytes, image decode via Pillow, size/page/dimension limits)
- [ ] Multi-image upload as single document (ordered pages)
- [ ] `processing_jobs` table + background task dispatch
- [ ] PyMuPDF text extraction (text-layer pages)
- [ ] Chunking logic (token-aware, ~800 tokens, ~120 overlap, page_start/page_end)
- [ ] Embedding call + pgvector insert (idempotent — no duplicate chunks)
- [ ] Document status transitions: `uploaded → processing → ready | failed`
- [ ] Delete endpoint (storage object + chunks + embeddings + metadata, tolerate partial failure)
- [ ] Frontend: documents list page (paginated, filter by subject), document detail, status display, retry failed
- [ ] Tests: upload validation, chunking, idempotent re-run, deletion cleanup
- [ ] Update PROGRESS.md, commit
