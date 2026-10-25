# AI Study Assistant

A full-stack web app for students: upload PDFs and photos of handwritten notes, ask questions answered with real citations (document + page), generate notes and quizzes, and follow a study plan.

## Tech Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form + Zod
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- **Database:** PostgreSQL + pgvector (Supabase or local Docker)
- **AI:** Google Gemini (transcription, embeddings, Q&A, notes, quizzes)
- **Auth:** Supabase Auth (JWT verification via JWKS)
- **Storage:** Supabase Storage (private bucket, short-lived signed URLs)

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- A Supabase project (production) or Docker (local Postgres)
- A Google Gemini API key

### 1. Supabase

1. Create a Supabase project.
2. In the SQL editor, enable pgvector:
   ```sql
   create extension if not exists vector;
   ```
3. Create a **private** Storage bucket named `documents` (or set `STORAGE_BUCKET`).
4. Enable Email/Password auth under Authentication.
5. Copy these values from Project Settings:
   - Project URL
   - Anon/publishable key (safe for the browser)
   - Service role key (**server only**, never expose to the browser)
   - JWKS URL: `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`

### 2. Gemini

1. Create an API key in Google AI Studio.
2. Set `GEMINI_API_KEY`.
3. `GEMINI_MODEL` defaults to `gemini-2.5-flash`; embeddings use `gemini-embedding-001` at 768 dimensions.
4. Gemini quota and transient failures are retried with a bounded budget and surfaced as clear errors. OCR and AI usage is capped by the configured limits.

### 3. Backend

```bash
cd backend
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt

copy .env.example .env
# Fill in DATABASE_URL, DATABASE_URL_SYNC, SUPABASE_*, GEMINI_*

# Run migrations (requires Postgres running)
python -m alembic upgrade head

# Start dev server
uvicorn app.main:app --reload
```

**Required environment variables:**

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | Sync connection string for Alembic (`postgresql://...`) |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon/publishable key |
| `SUPABASE_JWKS_URL` | Project JWKS endpoint for JWT verification |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only key for Storage writes/signed URLs |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Gemini generation model (default: `gemini-2.5-flash`) |
| `GEMINI_TIMEOUT_SECONDS` | Per-call timeout (default: 60) |
| `GEMINI_MAX_RETRIES` | Bounded retry count (default: 2) |
| `EMBEDDING_MODEL` | Gemini embedding model (default: `gemini-embedding-001`) |
| `EMBEDDING_DIM` | Embedding vector dimension (default: `768`) |
| `STORAGE_BUCKET` | Private Supabase Storage bucket (default: `documents`) |
| `OCR_LIMIT_PAGES_PER_DOC` | Max pages per document for OCR (default: 50) |
| `OCR_LIMIT_PAGES_PER_USER_PER_DAY` | Daily OCR page limit per user (default: 100) |
| `OCR_FALLBACK_ENABLED` | Enable Tesseract fallback (default: false) |
| `RATE_LIMIT_UPLOADS_PER_MINUTE` | Per-user upload limit (default: 10; 0 disables) |
| `RATE_LIMIT_AI_PER_MINUTE` | Per-user AI limit (default: 20; 0 disables) |
| `RATE_LIMIT_PROCESSING_PER_MINUTE` | Reserved for processing limits (default: 10) |
| `ENVIRONMENT` | `development` or `production`; production fails fast on missing required config |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |

### 4. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
# Fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL

npm run dev
```

**Required environment variables:**

| Variable | Description |
|---|---|
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/publishable key |
| `VITE_API_URL` | Backend API URL (default: `http://localhost:8000/api`) |

## Running Tests

```bash
# Backend (run the tests/ directory explicitly; scripts/smoke_test.py needs live env)
cd backend
venv/Scripts/python -m pytest tests/ -v

# Frontend typecheck and production build
cd frontend
npx tsc -p tsconfig.json --noEmit --incremental false
npm run build
```

Frontend component tests are not yet configured; the frontend gate is TypeScript + production build.

## Security and Privacy

- All API routes except `/api/health` require a Supabase JWT.
- Every resource query is scoped to the authenticated owner.
- Supabase URL and anon key are the only Supabase values shipped to the browser. The service role key stays on the backend.
- Document storage is private. Page images are exposed only through short-lived signed URLs.
- Deleting a document removes its Storage objects and database rows; storage failures are logged without blocking row deletion.
- Uploads and AI endpoints are rate-limited per user. The limiter is process-local; use a shared store such as Redis for multi-instance deployments.
- External Gemini calls have timeouts and bounded retries. Quota/transient failures return clear errors.
- Tokens and document text are not logged.

## OCR Disclaimer

OCR output accuracy depends on image quality and handwriting legibility. Handwritten notes may contain transcription errors. Always review flagged pages (marked "Needs Review") before relying on extracted text for study purposes.

Page images are sent to the Gemini API for transcription. This is documented for privacy transparency.

## Deployment Notes

### Backend

1. Provision PostgreSQL with the pgvector extension.
2. Set all backend environment variables in the host's secret manager.
3. Run `python -m alembic upgrade head` during release.
4. Start with:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Expose `/api/health` for health checks.
6. Set `ALLOWED_ORIGINS` to the exact frontend origin(s); do not use `*` with credentials.
7. Keep `SUPABASE_SERVICE_ROLE_KEY` and `GEMINI_API_KEY` server-side only.
8. For multiple backend instances, replace the in-memory rate limiter with a shared Redis-backed implementation.

### Frontend

1. Build with `npm run build`.
2. Deploy `frontend/dist`.
3. Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_API_URL` at build time.
4. Configure SPA fallback so client-side routes resolve to `index.html`.

### Background work

Document processing runs through FastAPI background tasks after upload. For production workloads, move ingestion to a durable worker/queue so retries survive process restarts.

## Known Limitations

- Live Supabase DB/storage and live Gemini calls are not verified in this environment; the Supabase pooler has been unavailable and no live smoke test has been run.
- PyMuPDF (PDF text extraction) may fail on Windows due to DLL loading policies.
- Embeddings are placeholder zeros when no Gemini API key is configured.
- OCR accuracy for handwriting varies; review flagged pages.
- Rate limiting is in-memory and per process.
- The pinned `google-generativeai` SDK is end-of-support; migrating to `google.genai` is a follow-up.
- Frontend automated component tests are not configured yet.
- Large frontend bundle (~866 kB minified) currently ships as a single chunk.

## Phases

- Phase 1: Foundation (repo, docker, config, models, auth, subjects CRUD)
- Phase 2: Documents (upload, validation, CRUD, chunking)
- Phase 3: OCR (Gemini vision provider, Tesseract fallback, page review/edit UI)
- Phase 4: Tutor (RAG, grounded answers, citations)
- Phase 5: Notes + Quizzes
- Phase 6: Study Planner + Dashboard
- Phase 7: Hardening
