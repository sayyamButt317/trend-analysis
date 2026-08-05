"""LinkedIn automation safety limits to reduce account block risk."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Any

logger = logging.getLogger(__name__)

# Practical caps used by competitor analysis nodes.
USER_EMPLOYEE_LIMIT = int(os.getenv("LINKEDIN_USER_EMPLOYEE_LIMIT") or 100)
COMPETITOR_EMPLOYEE_LIMIT = int(os.getenv("LINKEDIN_COMPETITOR_EMPLOYEE_LIMIT") or 20)


def linkedin_safety_config(runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = runtime or {}
    return {
        "page_delay_sec": float(
            os.getenv("LINKEDIN_PAGE_DELAY_SEC") or runtime.get("linkedin_page_delay_sec") or 4.0
        ),
        "page_delay_jitter_sec": float(os.getenv("LINKEDIN_PAGE_DELAY_JITTER_SEC") or 2.0),
        "max_pages_per_session": int(
            os.getenv("LINKEDIN_MAX_PAGES_PER_SESSION") or runtime.get("linkedin_max_pages_per_session") or 8
        ),
        "max_posts_playwright": int(os.getenv("LINKEDIN_MAX_POSTS_PLAYWRIGHT") or 5),
        "max_employees_playwright": int(
            os.getenv("LINKEDIN_MAX_EMPLOYEES_PLAYWRIGHT") or USER_EMPLOYEE_LIMIT
        ),
        "max_jobs_playwright": int(os.getenv("LINKEDIN_MAX_JOBS_PLAYWRIGHT") or 5),
        "reuse_session": os.getenv("LINKEDIN_REUSE_SESSION", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        "session_file": (os.getenv("LINKEDIN_SESSION_FILE") or ".cache/linkedin_session.json").strip(),
        "slow_mo_ms": int(os.getenv("LINKEDIN_SLOW_MO_MS") or 100),
        "warm_up_browser": os.getenv("LINKEDIN_WARM_UP", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        "scrape_competitors_with_playwright": os.getenv("LINKEDIN_SCRAPE_COMPETITORS", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        "max_playwright_competitors": int(os.getenv("LINKEDIN_MAX_PLAYWRIGHT_COMPETITORS") or 2),
        "user_employee_limit": USER_EMPLOYEE_LIMIT,
        "competitor_employee_limit": COMPETITOR_EMPLOYEE_LIMIT,
    }


async def linkedin_human_delay(safety: dict[str, Any]) -> None:
    delay = safety["page_delay_sec"] + random.uniform(0, safety["page_delay_jitter_sec"])
    logger.debug("LinkedIn safety delay: %.1fs", delay)
    await asyncio.sleep(delay)


def clamp_playwright_limits(
    *,
    post_limit: int,
    employee_limit: int,
    job_limit: int,
    safety: dict[str, Any] | None = None,
) -> tuple[int, int, int]:
    cfg = safety or linkedin_safety_config()
    return (
        min(post_limit, cfg["max_posts_playwright"]),
        min(employee_limit, cfg["max_employees_playwright"]),
        min(job_limit, cfg["max_jobs_playwright"]),
    )
