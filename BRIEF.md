AI Study Assistant — Agent Build Brief
You are building a working AI Study Assistant web app: students upload their own PDFs, ask questions answered with real citations (document + page), generate notes and quizzes, and follow a study plan. Work as a careful senior full-stack engineer. Real functionality over breadth.
0. Working rules (read first)
Work in small vertical slices. Finish one phase end to end (backend + frontend + tests) before the next. Do NOT scaffold everything first.
Stop at the end of every phase. Commit, update `PROGRESS.md`, report what works / what failed / what is next, then wait for my "continue". Do not run through all phases in one go.
Keep `PROGRESS.md` at the repo root as your memory: current phase, completed items, decisions made (with reasons), known issues, exact commands to run and test. Re-read it at the start of every session.
Never fake anything. No hardcoded AI responses, fake stats, or decorative buttons. Gemini is mocked ONLY in automated unit tests; the app itself must call the real provider or fail with a clear "not configured" error.
Report test results honestly. Run tests and paste the real output summary. If something is untested or needs live credentials, say so.
Credentials: you cannot create my Supabase project or Gemini key. Build against environment variables, use a local Postgres+pgvector (Docker) for development and tests, and tell me exactly what I must configure when you need live services. Never invent keys.
Ask me only when a decision genuinely cannot be made safely. Otherwise decide, and log the decision in `PROGRESS.md`.
First inspect the existing repo and preserve useful work. Don't overwrite files blindly.
1. MVP scope
In scope (v1): auth, subjects, PDF and image upload + ingestion (including OCR for handwritten notes, photos, and scanned PDFs), RAG tutor with citations and persistent chats, summaries/revision notes, quizzes with backend grading, rule-based study planner, dashboard.
Out of scope for v1 (do not build unless I ask): previous-year paper analysis and topic-frequency charts, AI grading of short answers, handwritten math/diagram understanding (OCR text only), chapter detection, syllabus topic hierarchy import, multi-user sharing, payments, mobile apps.
Pages where OCR returns nothing usable are flagged `needs_review` or failed with a clear message, never silently marked fine.
2. Tech stack
Frontend: React, TypeScript, Vite, React Router, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form + Zod, Recharts, Vitest + React Testing Library.
Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PyMuPDF, Pytest.
Data: Supabase Auth, Supabase Postgres + pgvector, private Supabase Storage bucket.
AI: Google Gemini (answers, summaries, quiz generation) and a Gemini embedding model, behind a small provider interface (`generate`, `generate_structured`, `embed`).
OCR: Gemini multimodal vision as the primary OCR engine (handles handwriting far better than Tesseract), behind an `OcrProvider` interface (`transcribe_page(image_bytes) -> text + flags`) so it can be swapped. Optional Tesseract (`pytesseract`) fallback for clean printed text only; do not rely on it for handwriting. Pillow for image validation/normalization.
Background jobs: keep it simple — a `processing_jobs` table (or FastAPI `BackgroundTasks` plus a startup sweep) with status, attempts, last_error, bounded retries. No Celery/Redis unless justified in `PROGRESS.md`.
Dev infra: `docker-compose.yml` with Postgres + pgvector for local dev and integration tests.
Before coding, verify against current docs: the Gemini SDK package and call signatures, available model names, the embedding model's output dimension (choose one dimension, make it config, and size the pgvector column from it), and Supabase JWT verification (prefer JWKS/asymmetric verification; fall back to the project's documented method). Log what you chose.
3. Repository layout
```
ai-study-assistant/
  frontend/   (src/{components,layouts,pages,hooks,services,types,utils,routes,tests})
  backend/    (app/{api,core,db,models,schemas,services,repositories,workers,ai,rag,quizzes,study_planner,tests}, alembic/)
  docker-compose.yml
  PROGRESS.md
  README.md
  .gitignore
```
Each of `frontend/` and `backend/` has its own `.env.example`.
4. Core requirements
Auth
Register, login, logout, session persistence on refresh, protected routes, profile. The backend verifies the Supabase access token on every protected endpoint and derives the user ID from it. Never trust a client-supplied user ID. Every resource (and nested resource) is scoped to its owner.
Documents
Upload PDFs and images (JPG, PNG, WebP; HEIC only if conversion is easy), attach to a subject, list (paginated, filter by subject), detail page, status, retry failed, delete.
Validate real file content (PDF magic bytes / image decodes with Pillow, page-count, file-size, and image-dimension limits — all configurable). Strip EXIF. Handle empty, corrupt, and encrypted files.
Multi-image uploads: several photos can be uploaded together as one document (e.g. a set of handwritten notes); the order the user gives becomes the page order.
States: `uploaded → processing → ready | failed`. Only mark `ready` after extraction, chunking, and embedding all succeed.
Delete removes the storage object, chunks, embeddings, and related metadata, in a documented order that tolerates partial failure.
Ingestion pipeline
For each page (PDF page or uploaded image), pick the extraction path: if a PDF page has a usable text layer, use PyMuPDF text; otherwise (scanned PDF page, or an image) render at ~200 DPI (PDF) or normalize (image) and OCR it with the `OcrProvider`. Record per page: `page_number`, `text`, `source` (`text_layer` | `ocr`), `needs_review`, `user_edited`. Keep page numbers → token-aware chunks (start ~800 tokens, ~120 overlap, configurable; a chunk may span pages, store `page_start`/`page_end`) → batch-embed (respect rate limits, retry with backoff) → store in `document_chunks` with a pgvector HNSW or IVFFlat cosine index. Idempotent retries: re-running a job must not create duplicate chunks. OCR runs page by page with bounded concurrency, retries on transient errors, and resumes from the failed page rather than redoing finished pages.
OCR rules
The OCR prompt must demand verbatim transcription: no correcting, summarizing, or inventing; mark unreadable words as `[illegible]`. Pages with many `[illegible]` markers, very short output, or a provider-reported low-quality signal are set `needs_review`.
Review step: the document detail page shows each OCR'd page next to its original image/page render, lets the student edit the text, and re-run OCR for a page. Edited text is re-chunked and re-embedded. A document with `needs_review` pages may still be `ready`, but those pages show a visible "OCR – unverified" badge, and citations from OCR pages show it too.
Limits: cap OCR pages per document and per user per day (configurable) to control cost and quota. Tell the user clearly if a limit is hit.
Handwriting accuracy varies. The README must state that OCR output can contain errors and that answers from handwritten notes are only as good as the transcription.
Privacy: page images are sent to the Gemini API. Document this in the README and the upload UI.
Retrieval + grounded answers
Vector search restricted to the caller's documents and the selected subject/document filters. Configurable top-k and a minimum similarity threshold.
Prompt Gemini with the question + retrieved chunks, each labelled with a chunk ID. Treat chunk text as untrusted reference material, never as instructions.
Require structured output: answer text + citations referencing chunk IDs. Validate that every cited ID was actually retrieved; resolve document name and page from the database, not from model output. Drop or reject invalid citations.
If nothing relevant is retrieved or the model says the evidence is insufficient, return an explicit "the uploaded materials don't cover this" result. Do not guess.
Follow-up questions use recent conversation history plus fresh retrieval.
Chat
Sessions and messages persisted in Postgres. Endpoints: create/list/delete sessions, list/post messages. Handle loading, errors, and provider rate limits in the UI.
Notes
Generate summary (short/detailed), key concepts, definitions, and revision notes for a selected document or page range, grounded in extracted text (map-reduce for long documents). Save, list, view, delete notes.
Quizzes
Choose subject/document, count, difficulty, type (MCQ, short answer).
Validate generated questions with Pydantic (MCQ needs question, options, one correct answer, explanation). Store source document/page references.
Answer keys must never appear in pre-submission API responses — use separate response schemas, and test it.
Grade on the backend. Short answers: simple self-check against a stored model answer shown after submission (no AI grading in v1).
Store attempts and per-question responses; show score, accuracy, mistakes with explanations, and per-topic performance; allow reviewing past attempts.
Study planner
Inputs: subject, exam date, topics (user-entered list), importance, daily minutes, preferred days. Rule-based scheduler using exam proximity, importance, past quiz performance, and remaining workload, with revision slots. Never schedule after the exam date; respect daily limits; persist plans/tasks; mark complete/incomplete; daily and weekly views; regenerate future tasks without erasing completed history; show a plain-language reason for each priority.
Dashboard
Computed from real data: document counts by status, upcoming exams, today's tasks, plan progress, recent quiz scores, weak topics, recent materials. Graceful empty state for new users.
5. Data model
Tables: `profiles`, `subjects`, `documents`, `document_pages` (per-page text, source, needs_review, user_edited, storage path of the page image when OCR'd), `document_chunks`, `processing_jobs`, `chat_sessions`, `chat_messages`, `notes`, `quizzes`, `quiz_questions`, `quiz_attempts`, `quiz_responses`, `study_plans`, `study_tasks`. (Topics can be a plain `topic` string / small `topics` table for v1; no hierarchy.)
UUID primary keys, foreign keys with sensible `ON DELETE`, timestamps, unique constraints, indexes on owner + filter columns. JSONB only for options/citations-type data. Alembic migrations must apply cleanly on an empty database. Consider enabling Supabase RLS as defense in depth, but backend authorization checks remain the primary control.
6. Frontend routes
`/login`, `/register`, `/onboarding`, `/dashboard`, `/subjects`, `/subjects/:subjectId`, `/documents`, `/documents/:documentId`, `/tutor`, `/tutor/:sessionId`, `/notes`, `/quizzes`, `/quizzes/:quizId`, `/quizzes/:quizId/results`, `/study-planner`, `/settings`, and a not-found route.
Responsive sidebar layout, loading skeletons, empty and error states, confirmation dialogs for destructive actions, form validation, accessible labels and keyboard use. Every visible control must work; don't ship placeholders.
7. Security and reliability
Token verification on all protected routes; ownership checks everywhere; secrets only in env vars (never in the browser — only the Supabase URL and publishable key); private bucket with short-lived signed URLs; strict CORS origins; rate limits on uploads and AI endpoints; timeouts and bounded retries on external calls; handle Gemini quota/transient errors with clear user messages; don't log tokens or document text; consistent error response shape; app reports missing configuration clearly at startup. List remaining limitations in the README.
8. Testing
Unit (Gemini mocked): OCR path selection (text layer vs OCR), OCR prompt/response handling, `needs_review` flagging, resume-from-failed-page, multi-image page ordering, chunking and page mapping, citation validation, insufficient-evidence path, quiz schema validation, grading, topic-performance math, planner constraints (exam date, daily limit, preserved history), job retry/idempotency.
Integration (real Postgres+pgvector via Docker, Gemini mocked): migrations on a clean DB, cross-user isolation on every resource type, retrieval authorization, document deletion cleanup, answer-key protection in API responses.
Frontend: protected routes, auth forms, key loading/error/empty/success states.
Live smoke test (needs my real keys): clearly separated, documented script that uploads a sample PDF and a photo of handwritten notes, waits for `ready`, asks a question, and checks the citation page. Tell me when it's time to run it.
9. Phases (stop after each)
Foundation: repo, docker-compose, config validation, models + migrations, health check, Supabase Auth on frontend and token verification on backend, subjects CRUD, protected routing.
Documents: upload, validation, storage, job processing, text-layer extraction, chunking, embeddings, status UI, retry, delete.
OCR: image and multi-image uploads, scanned-PDF page rendering, `OcrProvider` with Gemini vision, per-page review/edit UI, re-embedding on edit, OCR limits. Stop here and let me test with my own handwritten samples before moving on.
Tutor: retrieval, grounded answers, citation validation, chat persistence and UI.
Notes + quizzes: generation, storage, backend grading, results, performance tracking.
Planner + dashboard: scheduler, task tracking, dashboard from real data.
Hardening: rate limits, security review, responsive/accessibility pass, full test run, README with Supabase + Gemini setup, deployment notes.
After each phase: run its tests, fix failures, verify migrations on a clean DB, verify the frontend talks to the real backend, update `PROGRESS.md` and README, and report.
10. Definition of done (v1)
A student can register, log in, create a subject, upload a PDF or photos of handwritten notes, see them become `ready` (reviewing and correcting OCR text where flagged), ask questions and get verifiable cited answers that persist across refresh, generate and save notes, take a quiz graded on the backend, generate a study plan and tick off tasks, and see a dashboard built from real data. Other users can never access their data. Migrations apply on a clean database, setup instructions are reproducible, and every claim of "tested" is backed by output you actually ran.
11. Final delivery
Repo structure, features verified vs. unverified, migration and start commands (frontend, backend, worker), env var list, Supabase + Gemini setup steps, test commands with real results, deployment notes, known limitations, and any manual configur
ation still needed.
Start now: inspect the repo, write the initial `PROGRESS.md` with a checklist and the decisions from section 2, then complete Phase 1 and stop.