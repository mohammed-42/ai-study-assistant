from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.models.profile import Profile

bearer_scheme = HTTPBearer(auto_error=False)

_jwks_cache: dict[str, Any] = {}
_jwks_expires: float = 0.0
_JWKS_TTL = 3600  # 1 hour


async def _get_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_expires
    now = time.time()
    if now < _jwks_expires and _jwks_cache:
        return _jwks_cache

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(settings.SUPABASE_JWKS_URL)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("keys"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWKS has no keys",
        )

    _jwks_cache = data
    _jwks_expires = now + _JWKS_TTL
    return data


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing authorization token",
        )

    token = credentials.credentials

    try:
        jwks = await _get_jwks()
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"could not fetch Supabase keys: {exc}",
        ) from exc

    from jose import jwt, JWTError

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg not in ("RS256", "ES256"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"unsupported token algorithm: {alg}",
            )
        kid = header.get("kid")
        key = _find_key(jwks, kid)
        payload = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
        )
    except HTTPException:
        raise
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        ) from exc

    sub: str | None = payload.get("sub")
    email: str | None = payload.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token missing sub or email",
        )

    stmt = select(Profile).where(Profile.sub == sub)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        # Auto-provision on first login
        profile = Profile(sub=sub, email=email)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


def _find_key(jwks: dict, kid: str | None) -> str:
    """Return the PEM-formatted public key matching kid."""
    from jose import jwk

    keys = jwks.get("keys", [])
    target = next((k for k in keys if k.get("kid") == kid), None)
    if target is None and keys:
        target = keys[0]
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="no matching JWKS key found",
        )
    key = jwk.construct(target)
    return key.to_pem().decode()
