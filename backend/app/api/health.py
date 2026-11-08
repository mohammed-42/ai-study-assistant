from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.base import get_session_maker

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
