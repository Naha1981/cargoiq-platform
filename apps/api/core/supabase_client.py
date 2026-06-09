"""
CargoIQ — Supabase client factory.
Two clients: anon (user-scoped, RLS enforced) and service role (admin ops).
"""
from supabase import create_client, Client
from functools import lru_cache
from .config import settings


@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """Service role client — bypasses RLS. Use ONLY for system operations."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def get_supabase_user(jwt_token: str) -> Client:
    """User-scoped client — respects RLS. Use for all user-facing operations."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(access_token=jwt_token, refresh_token="")
    return client
