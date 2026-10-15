from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health_router, subjects_router, documents_router, upload_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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


@app.on_event("startup")
async def startup():
    from app.db.base import engine, init_db
    from app.core.config import settings as s

    if not s.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set — cannot start")
    await init_db()
