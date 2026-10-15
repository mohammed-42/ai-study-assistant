from __future__ import annotations

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.profile import Profile

bearer_scheme = HTTPBearer(auto_error=False)


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
    # Fetch Supabase JWKS and verify JWT
    jwks_url = "https://api.supabase.com/auth/v1/keys"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            jwks = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"could not fetch Supabase keys: {exc}",
        ) from exc

    from jose import jwt, JWTError

    try:
        alg = _get_algorithm(jwks, token)
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        # For Supabase, use the key matching the token's kid
        kid = header.get("kid")
        key = _find_key(jwks, kid)
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience="https://api.supabase.com/auth/v1/token/v2",
        )
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


def _get_algorithm(jwks: dict, token: str) -> str:
    # Supabase uses RS256
    return "RS256"


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
    key = jwk.JWK(**target)
    return key.to_pem().decode()
