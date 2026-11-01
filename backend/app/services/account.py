from __future__ import annotations

from app.core.config import settings


def delete_auth_user(auth_user_id: str) -> None:
    """Delete the Supabase auth user with the backend-only service role key."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase admin is not configured")

    from supabase import create_client

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    client.auth.admin.delete_user(auth_user_id)
