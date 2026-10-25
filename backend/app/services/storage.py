"""Supabase Storage helpers for private objects and signed URLs."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def storage_is_configured() -> bool:
    return bool(
        settings.SUPABASE_URL
        and settings.SUPABASE_SERVICE_ROLE_KEY
        and settings.STORAGE_BUCKET
    )


def get_storage_client() -> Any:
    if not storage_is_configured():
        raise RuntimeError("Supabase Storage is not configured")
    from supabase import create_client

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def create_signed_url(storage_key: str, expires_in: int = 3600) -> str:
    """Return a short-lived signed URL for a private storage object."""
    storage = get_storage_client()
    result = storage.storage.from_(settings.STORAGE_BUCKET).create_signed_url(
        storage_key,
        expires_in,
    )

    url = None
    if isinstance(result, dict):
        url = (
            result.get("signedURL")
            or result.get("signed_url")
            or result.get("url")
        )
    elif isinstance(result, str):
        url = result

    if not url:
        raise RuntimeError("Storage did not return a signed URL")
    return url


def delete_document_objects(
    owner_id: uuid.UUID,
    document_id: uuid.UUID,
    storage_key: str | None = None,
) -> int:
    """Delete all objects for a document. Failures are logged, not raised."""
    if not storage_is_configured():
        return 0

    expected_prefix = f"user/{owner_id}/{document_id}"
    folder = expected_prefix
    if storage_key and "/" in storage_key:
        candidate = storage_key.rsplit("/", 1)[0]
        if candidate.startswith(expected_prefix):
            folder = candidate

    try:
        storage = get_storage_client()
        bucket = storage.storage.from_(settings.STORAGE_BUCKET)
        files = bucket.list(folder)
        keys = [
            f"{folder}/{item['name']}"
            for item in files
            if item.get("name")
        ]
        if keys:
            bucket.remove(keys)
        return len(keys)
    except Exception as exc:
        logger.warning(
            "Storage cleanup failed for document %s (%s): %s",
            document_id,
            folder,
            exc,
        )
        return 0
