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
     `STORAGE_BUCKET`, `OCR_LIMIT_PAGES_PER_DOC`,
     `OCR_LIMIT_PAGES_PER_USER_PER_DAY`, `ALLOWED_ORIGINS`.
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

## Known limitations

- OCR is not 100% accurate, especially for handwriting. Review the extracted text after upload.
- Rate limiting is in-memory and per process; use a shared store for multiple instances.
- Free-tier Gemini quotas can temporarily block OCR and embeddings; retry later.
