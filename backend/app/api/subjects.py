from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.profile import Profile
from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectOut, SubjectUpdate

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("/", response_model=list[SubjectOut])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    stmt = (
        select(Subject)
        .where(Subject.owner_id == user.id)
        .order_by(desc(Subject.created_at))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=SubjectOut, status_code=201)
async def create_subject(
    body: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    subject = Subject(owner_id=user.id, name=body.name, description=body.description)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.get("/{subject_id}", response_model=SubjectOut)
async def get_subject(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    from uuid import UUID

    subject = await _get_owner_subject(db, UUID(subject_id), user.id)
    return subject


@router.patch("/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: str,
    body: SubjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    subject = await _get_owner_subject(db, UUID(subject_id), user.id)
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(subject, key, value)
    await db.commit()
    await db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=204)
async def delete_subject(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    subject = await _get_owner_subject(db, UUID(subject_id), user.id)
    await db.delete(subject)
    await db.commit()
    return None


async def _get_owner_subject(db: AsyncSession, subject_id: "uuid.UUID", owner_id: "uuid.UUID"):
    from uuid import UUID

    stmt = select(Subject).where(
        Subject.id == subject_id,
        Subject.owner_id == owner_id,
    )
    result = await db.execute(stmt)
    subject = result.scalar_one_or_none()
    if subject is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="subject not found",
        )
    return subject
