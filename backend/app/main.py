from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health_router, subjects_router, documents_router, upload_router, pages_router, chat_router, notes_router, quizzes_router, planner_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.base import init_db
    from app.core.config import settings as s

    if not s.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set — cannot start")
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(subjects_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(chat_router)
app.include_router(notes_router, prefix="")
app.include_router(quizzes_router, prefix="")
app.include_router(planner_router, prefix="")
