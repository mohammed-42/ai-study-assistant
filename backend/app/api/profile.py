from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services.account import delete_auth_user
from app.services.storage import delete_user_objects

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileOut)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    stmt = select(Profile).where(Profile.id == user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="profile not found",
        )
    return profile


@router.put("/profile", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    stmt = select(Profile).where(Profile.id == user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="profile not found",
        )

    profile.full_name = body.full_name
    await db.commit()
    await db.refresh(profile)
    return profile


@router.delete("/account", status_code=204)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    try:
        delete_user_objects(user.id)
    except Exception as exc:
        logger.warning("Account storage cleanup failed for %s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Account not deleted: failed to remove stored files. "
                "Some files may have been removed; no profile data was deleted."
            ),
        ) from exc

    try:
        await db.execute(delete(Profile).where(Profile.id == user.id))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.warning("Account profile deletion failed for %s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Account not fully deleted: stored files were removed, but profile "
                "deletion failed. No login account was deleted."
            ),
        ) from exc

    try:
        delete_auth_user(user.sub)
    except Exception as exc:
        logger.warning("Account auth deletion failed for %s: %s", user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Account data and stored files were deleted, but the login account "
                "could not be removed. Signing in again may recreate a profile; "
                "contact support."
            ),
        ) from exc

    return None
