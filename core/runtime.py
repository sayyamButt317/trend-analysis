from __future__ import annotations
import os
from typing import Any


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def runtime_profile() -> dict[str, Any]:
    return {
        "serverless": False,
        "competitor_limit": _env_int("COMPETITOR_LIMIT", 10),
        "post_limit": _env_int("COMPETITOR_POST_LIMIT", 10),
        "skip_linkedin": False,
        "skip_playwright": False,
        "discovery_candidate_multiplier": 2,
        "max_tavily_queries": _env_int("MAX_TAVILY_QUERIES", 10),
        "max_firecrawl_queries": _env_int("MAX_FIRECRAWL_QUERIES", 4),
        "max_social_tavily_lookups": _env_int("MAX_SOCIAL_TAVILY_LOOKUPS", 15),
        "request_delay_seconds": 1.0,
        "max_duration_sec": None,
        "linkedin_page_delay_sec": 4.0,
        "linkedin_max_pages_per_session": 6,
        "linkedin_scrape_competitors": False,
    }
