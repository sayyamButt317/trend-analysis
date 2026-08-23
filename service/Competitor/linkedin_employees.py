"""Parse LinkedIn company headcount and enrich competitor records."""

from __future__ import annotations

import re
from typing import Any


_EMPLOYEE_RANGE_RE = re.compile(
    r"(?P<lo>[\d,]+)\s*[-–]\s*(?P<hi>[\d,]+)\s*employees?",
    re.I,
)
_EMPLOYEE_PLUS_RE = re.compile(
    r"(?P<n>[\d,]+)\+\s*employees?",
    re.I,
)
_EMPLOYEE_EXACT_RE = re.compile(
    r"(?P<n>[\d,]+)\s*employees?",
    re.I,
)
_EMPLOYEE_K_PLUS_RE = re.compile(
    r"(?P<n>[\d.]+)\s*k\+\s*employees?",
    re.I,
)


def _to_int(value: str) -> int:
    return int(str(value).replace(",", "").strip())


def parse_linkedin_company_size(company_size: str | None) -> dict[str, Any]:
    """Parse LinkedIn company size text into total employees estimate."""
    text = str(company_size or "").strip()
    if not text:
        return {
            "linkedin_company_size": None,
            "linkedin_total_employees": None,
            "linkedin_employee_range": None,
        }

    lower = text.lower()

    match = _EMPLOYEE_K_PLUS_RE.search(lower)
    if match:
        total = int(float(match.group("n")) * 1000)
        return {
            "linkedin_company_size": text,
            "linkedin_total_employees": total,
            "linkedin_employee_range": {"min": total, "max": None},
        }

    match = _EMPLOYEE_RANGE_RE.search(text)
    if match:
        lo = _to_int(match.group("lo"))
        hi = _to_int(match.group("hi"))
        return {
            "linkedin_company_size": text,
            "linkedin_total_employees": (lo + hi) // 2,
            "linkedin_employee_range": {"min": lo, "max": hi},
        }

    match = _EMPLOYEE_PLUS_RE.search(text)
    if match:
        total = _to_int(match.group("n"))
        return {
            "linkedin_company_size": text,
            "linkedin_total_employees": total,
            "linkedin_employee_range": {"min": total, "max": None},
        }

    match = _EMPLOYEE_EXACT_RE.search(text)
    if match:
        total = _to_int(match.group("n"))
        return {
            "linkedin_company_size": text,
            "linkedin_total_employees": total,
            "linkedin_employee_range": {"min": total, "max": total},
        }

    return {
        "linkedin_company_size": text,
        "linkedin_total_employees": None,
        "linkedin_employee_range": None,
    }


def enrich_linkedin_employee_fields(
    *,
    company_size: str | None = None,
    sampled_employees: list[dict[str, Any]] | None = None,
    linkedin_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach LinkedIn headcount fields to a competitor/user record."""
    size_label = company_size or (linkedin_analysis or {}).get("company_size")
    parsed = parse_linkedin_company_size(size_label)
    sampled = sampled_employees or []
    sampled_count = len(sampled)

    return {
        **parsed,
        "company_size": parsed["linkedin_company_size"],
        "employee_count": parsed["linkedin_total_employees"] if parsed["linkedin_total_employees"] is not None else sampled_count,
        "linkedin_profiles_sampled": sampled_count,
        "employees": sampled,
    }


def competitor_linkedin_summary(competitors: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate LinkedIn employee stats across competitors."""
    totals: list[int] = []
    with_size = 0
    for comp in competitors:
        total = comp.get("linkedin_total_employees")
        if total is not None:
            totals.append(int(total))
            with_size += 1

    return {
        "competitors_with_linkedin_headcount": with_size,
        "total_competitors": len(competitors),
        "avg_linkedin_employees": round(sum(totals) / len(totals)) if totals else None,
        "max_linkedin_employees": max(totals) if totals else None,
        "min_linkedin_employees": min(totals) if totals else None,
    }


async def fetch_company_size_tavily(
    company_name: str,
    *,
    linkedin_url: str | None = None,
) -> str | None:
    """Best-effort LinkedIn headcount label via Tavily when Playwright is unavailable."""
    from config.credential_config import config
    from scrapper.tavily_retry import tavily_search_with_retry

    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key or not company_name:
        return None

    slug_query = f'"{company_name}" linkedin company employees'
    if linkedin_url:
        slug_query = f'site:linkedin.com/company "{company_name}" employees'

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = tavily_search_with_retry(
            client,
            query=slug_query,
            search_depth="basic",
            max_results=5,
            count_as_linkedin=True,
        )
    except Exception:
        return None

    for item in response.get("results") or []:
        blob = " ".join(
            str(item.get(key) or "")
            for key in ("title", "content", "snippet", "raw_content")
        )
        for pattern in (_EMPLOYEE_RANGE_RE, _EMPLOYEE_PLUS_RE, _EMPLOYEE_K_PLUS_RE, _EMPLOYEE_EXACT_RE):
            match = pattern.search(blob)
            if match:
                start = max(0, match.start() - 10)
                end = min(len(blob), match.end() + 20)
                return blob[start:end].strip(" .,-")
    return None
