from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.document import Document, DocumentStatus
from app.models.profile import Profile
from app.models.subject import Subject
from app.schemas.document import DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])

# Configurable limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_PDF_MIME = ["application/pdf"]
ALLOWED_IMAGE_MIME = ["image/jpeg", "image/png", "image/webp"]
# Max files for multi_image upload
MAX_MULTI_IMAGE_FILES = 20


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    files: list[UploadFile] = File(...),
    subject_id: str = Query(...),
    doc_type: str = "pdf",
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    # Validate doc_type
    if doc_type not in ("pdf", "image", "multi_image"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid doc_type")

    # Validate subject ownership
    subject_stmt = select(Subject).where(Subject.id == uuid.UUID(subject_id), Subject.owner_id == user.id)
    subject_result = await db.execute(subject_stmt)
    if not subject_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")

    # multi_image: require 2+ files
    if doc_type == "multi_image":
        if len(files) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="multi_image requires at least 2 files",
            )
        if len(files) > MAX_MULTI_IMAGE_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"multi_image allows at most {MAX_MULTI_IMAGE_FILES} files",
            )

    # Validate and collect file contents
    contents: list[tuple[str, bytes, str]] = []  # (filename, bytes, mime)
    for file in files:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large (max 50MB)")

        if doc_type == "pdf":
            if len(files) == 1 and not content[:4] == b"%PDF":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid PDF file")
            mime = "application/pdf"
        elif doc_type == "image":
            from PIL import Image
            try:
                img = Image.open(io.BytesIO(content))
                if img.format not in ("JPEG", "PNG", "WEBP"):
                    raise ValueError("unsupported image format")
                mime = f"image/{img.format.lower()}"
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid image: {e}")
        else:  # multi_image
            from PIL import Image
            try:
                img = Image.open(io.BytesIO(content))
                if img.format not in ("JPEG", "PNG", "WEBP"):
                    raise ValueError("unsupported image format")
                mime = f"image/{img.format.lower()}"
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid image: {e}")

        contents.append((file.filename, content, mime))

    # Create document record
    doc_id = uuid.uuid4()
    first_name = contents[0][0]
    storage_key = f"user/{user.id}/{doc_id}/{first_name}"

    doc = Document(
        id=doc_id,
        owner_id=user.id,
        subject_id=uuid.UUID(subject_id),
        name=first_name,
        doc_type=doc_type,
        status=DocumentStatus.UPLOADED,
        storage_key=storage_key,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # TODO: Store files in Supabase Storage and trigger processing job

    return doc
