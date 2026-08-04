"""Runtime profile helpers for local vs serverless (Vercel) deployments."""

from __future__ import annotations

import os
from typing import Any


def is_vercel() -> bool:
    return bool(os.getenv("VERCEL"))


def is_serverless() -> bool:
    if is_vercel():
        return True
    return os.getenv("SERVERLESS_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def runtime_profile() -> dict[str, Any]:
    """Return deployment-specific limits and feature flags."""
    if is_serverless():
        return {
            "serverless": True,
            "competitor_limit": _env_int("SERVERLESS_COMPETITOR_LIMIT", 5),
            "post_limit": _env_int("SERVERLESS_POST_LIMIT", 5),
            "skip_linkedin": os.getenv("SERVERLESS_SKIP_LINKEDIN", "true").strip().lower()
            != "false",
            "skip_playwright": True,
            "discovery_candidate_multiplier": 2,
            "max_tavily_queries": 8,
            "max_firecrawl_queries": 4,
            "request_delay_seconds": 0.5,
            "max_duration_sec": _env_int("SERVERLESS_MAX_DURATION_SEC", 240),
        }
    return {
        "serverless": False,
        "competitor_limit": _env_int("COMPETITOR_LIMIT", 50),
        "post_limit": _env_int("COMPETITOR_POST_LIMIT", 10),
        "skip_linkedin": False,
        "skip_playwright": False,
        "discovery_candidate_multiplier": 3,
        "max_tavily_queries": 20,
        "max_firecrawl_queries": 8,
        "request_delay_seconds": 1.0,
        "max_duration_sec": None,
    }
