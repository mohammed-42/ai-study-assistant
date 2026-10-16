# AI Study Assistant

A full-stack web app for students: upload PDFs and photos of handwritten notes, ask questions answered with real citations (document + page), generate notes and quizzes, and follow a study plan.

## Tech Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form + Zod
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- **Database:** PostgreSQL + pgvector (Supabase or local Docker)
- **AI:** Google Gemini (transcription, embeddings, Q&A)
- **Auth:** Supabase Auth (JWT verification via JWKS)

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- Supabase project (for production) or Docker (for local dev)

### Backend

```bash
cd backend
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt

# Copy and fill environment variables
copy .env.example .env
# Edit .env with your real values

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
| `SUPABASE_ANON_KEY` | Supabase anon/public key |
| `SUPABASE_JWKS_URL` | Supabase JWKS endpoint for JWT verification |
| `GEMINI_API_KEY` | Google Gemini API key |
| `EMBEDDING_MODEL` | Gemini embedding model name (default: `text-embedding-004`) |
| `EMBEDDING_DIM` | Embedding vector dimension (default: `768`) |
| `STORAGE_BUCKET` | Supabase Storage bucket name |
| `OCR_LIMIT_PAGES_PER_DOC` | Max pages per document for OCR (default: 50) |
| `OCR_LIMIT_PAGES_PER_USER_PER_DAY` | Daily OCR page limit per user (default: 100) |
| `OCR_FALLBACK_ENABLED` | Enable Tesseract fallback (default: false) |

### Frontend

```bash
cd frontend
npm install
# Copy and fill environment variables
copy .env.example .env.local
# Edit .env.local with your real values

npm run dev
```

**Required environment variables:**

| Variable | Description |
|---|---|
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public key |
| `VITE_API_URL` | Backend API URL (default: `http://localhost:8000/api`) |

## Running Tests

```bash
# Backend tests
cd backend
venv/Scripts/python -m pytest tests/ -v

# Frontend tests
cd frontend
npm test
```

## OCR Disclaimer

OCR output accuracy depends on image quality and handwriting legibility. Handwritten notes may contain transcription errors. Always review flagged pages (marked "Needs Review") before relying on extracted text for study purposes.

Page images are sent to the Gemini API for transcription. This is documented for privacy transparency — no images are stored beyond what's necessary for the application.

## Known Limitations

- Local development defaults to SQLite; production requires PostgreSQL with pgvector
- PyMuPDF (PDF text extraction) may fail on Windows due to DLL loading policies
- Embeddings are placeholder zeros until Gemini API key is configured
- Supabase Storage integration is stubbed (files accepted but not persisted to cloud)

## Phases

- ✅ Phase 1: Foundation (repo, docker, config, models, auth, subjects CRUD)
- ✅ Phase 2: Documents (upload, validation, CRUD, chunking)
- ✅ Phase 3: OCR (Gemini vision provider, Tesseract fallback, page review/edit UI)
- ⏳ Phase 4: Tutor (RAG, grounded answers, citations)
- ⏳ Phase 5: Notes + Quizzes
- ⏳ Phase 6: Study Planner + Dashboard
- ⏳ Phase 7: Hardening
