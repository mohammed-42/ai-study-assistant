# AI Study Assistant

Upload PDFs or photos of handwritten notes, review the extracted text, ask questions with
document/page citations, generate notes and quizzes, and follow a study plan.

Stack: React + TypeScript + Vite frontend; FastAPI + SQLAlchemy + Alembic backend;
PostgreSQL + pgvector; Supabase Auth/Storage; Google Gemini for OCR, embeddings and generation.

## Setup

### 1. Supabase and Gemini

1. Create a Supabase project.
2. In the SQL editor, enable pgvector:
   ```sql
   create extension if not exists vector;
   ```
3. Create a **private** Storage bucket named `documents` (or set `STORAGE_BUCKET`).
4. Enable Email/Password auth and create a test user (used by the live smoke test).
5. Create a Gemini API key in Google AI Studio.
6. Create the backend `.env` from `backend/.env.example` and the frontend `.env.local`
   from `frontend/.env.example`. Fill the values locally; never commit them.
   - Backend names: `DATABASE_URL`, `DATABASE_URL_SYNC`, `SUPABASE_URL`,
     `SUPABASE_ANON_KEY`, `SUPABASE_JWKS_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
     `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`,
     `CHUNK_TARGET_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `STORAGE_BUCKET`,
     `OCR_LIMIT_PAGES_PER_DOC`, `OCR_LIMIT_PAGES_PER_USER_PER_DAY`,
     `ALLOWED_ORIGINS`.
   - Frontend names: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`.

### 2. Session pooler tip

Use the **Session pooler** connection string from Supabase Connect. Copy the host exactly:
the `aws-0` / `aws-1` prefix matters. Use a database password made of letters and numbers;
special characters must be URL-encoded in `DATABASE_URL` and `DATABASE_URL_SYNC`.

## Migrations

```bash
cd backend
venv/Scripts/python -m alembic upgrade head
```

If the database was created outside Alembic (tables already exist), stamp the current
revision first, then upgrade:

```bash
venv/Scripts/python -m alembic stamp <current_revision>
venv/Scripts/python -m alembic upgrade head
```

## Run

```bash
# Backend (http://localhost:8000)
cd backend
venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

## Tests

```bash
# Backend tests (mocked, hermetic)
cd backend
venv/Scripts/python -m pytest tests -q

# Frontend typecheck and production build
cd frontend
npx tsc -p tsconfig.json --noEmit --incremental false
npm run build
```

## Live smoke test

Start the backend, then run the smoke script with the live settings in `backend/.env.smoke`
(ignored by git). It creates and deletes only its own data.

```bash
cd backend
venv/Scripts/python scripts/smoke_test.py              # PDF path
venv/Scripts/python scripts/smoke_test.py --handwriting # handwriting OCR path
```

## Deployment

The backend is host-agnostic and ships as a Docker image (`backend/Dockerfile`); the
frontend is a static Vite build. Set `ENVIRONMENT=production` on the backend so startup
validation fails fast on missing config, wildcard CORS, `DEBUG=true`, and disables API docs.
Run `alembic upgrade head` against the production database before serving traffic.

### Backend (Render or Fly.io)

- Render: create a Web Service from this repo with Root Directory `backend`, Runtime
  `Docker`, Dockerfile path `Dockerfile`, and health check path `/api/health`. Use a
  pre-deploy command to run migrations.
- Fly.io: `cd backend && fly launch` (or `fly deploy`) to build the same Dockerfile; set the
  health check to `/api/health`.
- The container listens on `$PORT`, runs as a non-root user, and health-checks `/api/health`.
- Backend environment variable names: `DATABASE_URL`, `DATABASE_URL_SYNC`, `SUPABASE_URL`,
  `SUPABASE_ANON_KEY`, `SUPABASE_JWKS_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`,
  `GEMINI_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `CHUNK_TARGET_TOKENS`,
  `CHUNK_OVERLAP_TOKENS`, `STORAGE_BUCKET`, `OCR_LIMIT_PAGES_PER_DOC`,
  `OCR_LIMIT_PAGES_PER_USER_PER_DAY`, `ALLOWED_ORIGINS`, `ENVIRONMENT`, `DEBUG`, `APP_NAME`.

### Frontend (Vercel)

- Import the repo, set Root Directory `frontend`, framework Vite, build command
  `npm run build`, output directory `dist`. `vercel.json` provides the SPA fallback to
  `index.html`.
- Frontend environment variable names (build time): `VITE_API_URL`, `VITE_SUPABASE_URL`,
  `VITE_SUPABASE_ANON_KEY`. They are read only via `import.meta.env` at build time; no
  values are hardcoded.

### Supabase auth URLs

In Supabase Authentication > URL Configuration set the Site URL to the deployed frontend
URL and add the deployed frontend URL (and any preview URLs you use) to Redirect URLs.
Also add the deployed backend origin to `ALLOWED_ORIGINS`.

### Free-tier note

Free hosts (Render free web services, Fly machines that auto-stop) sleep when idle. The
first request after a period of inactivity can take tens of seconds while the instance
wakes.

## Known limitations

- OCR is not 100% accurate, especially for handwriting. Review the extracted text after upload.
- Rate limiting is in-memory and per process; use a shared store for multiple instances.
- Free-tier Gemini quotas can temporarily block OCR and embeddings; retry later.
