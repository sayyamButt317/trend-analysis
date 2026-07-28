import re
from functools import lru_cache

from fastapi import Depends
from supabase import Client, create_client

from config.credential_config import config, resolve_supabase_api_key


def _validate_supabase_config() -> tuple[str, str]:
    url = (config.SUPABASE_URL or "").strip()
    key = resolve_supabase_api_key()

    if not url or not key:
        publishable = (config.SUPABASE_KEY or "").startswith("sb_publishable_")
        hint = (
            "Set SUPABASE_SERVICE_ROLE_KEY (recommended) or SUPABASE_ANON_KEY to the "
            "JWT key from Supabase Dashboard → Project Settings → API. "
            "The sb_publishable_ key is not supported by supabase-py."
            if publishable
            else "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY)."
        )
        raise RuntimeError(hint)

    if not re.match(r"^https?://", url):
        raise RuntimeError(
            "SUPABASE_URL must be the Supabase API URL "
            "(https://<project-ref>.supabase.co), not a PostgreSQL connection string. "
            "Use DATABASE_URL for the postgres:// connection string."
        )
    return url, key


@lru_cache
def get_supabase() -> Client:
    url, key = _validate_supabase_config()
    return create_client(url, key)


def connect() -> None:
    get_supabase()


def close() -> None:
    get_supabase.cache_clear()


def get_supabase_client() -> Client:
    return get_supabase()


SupabaseDep = Depends(get_supabase_client)
