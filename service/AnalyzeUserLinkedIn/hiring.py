import logging
import re
from typing import Any

from config.credential_config import config
from scrapper.tavily_retry import is_tavily_unreachable_error, tavily_search_with_retry
from service.AnalyzeUserLinkedIn.session import LinkedInPlaywrightSession
from service.AnalyzeUserLinkedIn.urls import (
    build_company_urls_from_name,
    company_name_to_slug,
)

logger = logging.getLogger(__name__)

LINKEDIN_IN_RE = re.compile(r"linkedin\.com/in/([A-Za-z0-9_-]+)", re.I)
LINKEDIN_JOB_RE = re.compile(r"linkedin\.com/jobs/view/(\d{8,})", re.I)
_HIRING_TITLE_RE = re.compile(
    r"^(?P<company>.+?)\s+hiring\s+(?P<title>.+?)(?:\s+in\s+(?P<location>.+))?$",
    re.I,
)
_LISTICLE_HEADER_RE = re.compile(r"^#{2,4}\s+", re.M)
_COMPANY_SUFFIX_RE = re.compile(
    r"\b(inc|llc|ltd|limited|corp|corporation|co|company|group|pvt|private)\b\.?",
    re.I,
)

_EMPLOYEE_ROLE_QUERIES = (
    "founder OR CEO OR CTO OR director OR co-founder",
    "engineer OR developer OR architect OR devops",
    "manager OR lead OR product OR project",
    "designer OR marketing OR sales OR recruiter OR HR",
    "consultant OR analyst OR specialist OR associate",
)


def _normalize_company_tokens(company_name: str) -> list[str]:
    cleaned = _COMPANY_SUFFIX_RE.sub(" ", company_name or "")
    tokens = [t for t in re.split(r"[^a-z0-9]+", cleaned.lower()) if len(t) >= 3]
    return tokens


def _mentions_company(company_name: str, *texts: str) -> bool:
    name = (company_name or "").strip().lower()
    if not name:
        return True
    blob = " ".join((t or "") for t in texts).lower()
    if name in blob:
        return True
    tokens = _normalize_company_tokens(company_name)
    if not tokens:
        return False
    return all(token in blob for token in tokens)


def _looks_like_job_listicle(content: str) -> bool:
    text = content or ""
    if len(_LISTICLE_HEADER_RE.findall(text)) >= 3:
        return True
    employer_blocks = len(re.findall(r"####\s+\w+", text))
    return employer_blocks >= 3


def _parse_job_title(raw_title: str, company_name: str) -> tuple[str, str | None]:
    title = (raw_title or "").strip()
    if not title:
        return "Open role", None
    title = title.split(" | ")[0].strip()
    match = _HIRING_TITLE_RE.match(title)
    location: str | None = None
    if match:
        employer = (match.group("company") or "").strip()
        role = (match.group("title") or "").strip()
        location = (match.group("location") or "").strip() or None
        if role and _mentions_company(company_name, employer):
            title = role
    return title[:200], location


def merge_employees(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in list(existing) + list(incoming):
        url = (item.get("linkedin_url") or "").rstrip("/").lower()
        key = url or (item.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged

_merge_employees = merge_employees


async def scrape_employees_from_page(
    session: LinkedInPlaywrightSession,
    *,
    company_name: str,
    linkedin_url: str | None = None,
    limit: int,
) -> list[dict[str, Any]]:
    employees: list[dict[str, Any]] = []
    people_url = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)["people_url"]
    if not await session.navigate(people_url, purpose="company_employees"):
        return employees
    try:
        await session.page.evaluate(
            """async (limit) => {
            const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
            let last = 0;
            for (let i = 0; i < 12; i++) {
                window.scrollBy(0, Math.max(600, window.innerHeight * 0.9));
                await sleep(450);
                const count = document.querySelectorAll('a[href*="/in/"]').length;
                if (count >= limit || count === last) break;
                last = count;
            }
        }""",
            limit,
        )
        people_data = await session.page.evaluate(
            """(limit) => {
            const results = [];
            const seen = new Set();
            for (const a of document.querySelectorAll('a[href*="/in/"]')) {
                let href = (a.href || '').split('?')[0].replace(/\\/+$/, '');
                if (!href || seen.has(href)) continue;
                if (href.includes('/login') || href.includes('/signup')) continue;
                const card = a.closest('li') || a.closest('[data-view-name]') || a.parentElement;
                const lines = (card ? card.innerText : a.innerText || '')
                    .split('\\n').map(l => l.trim()).filter(Boolean);
                const name = lines[0] || '';
                if (!name || name.length < 2) continue;
                seen.add(href);
                results.push({
                    name,
                    designation: lines[1] || null,
                    linkedin_url: href,
                });
                if (results.length >= limit) break;
            }
            return results;
        }""",
            limit,
        )
        for item in people_data or []:
            employees.append({**item, "source": "linkedin_playwright"})
    except Exception:
        logger.debug("LinkedIn people scrape failed", exc_info=True)
    return employees[:limit]


async def scrape_jobs_from_page(
    session: LinkedInPlaywrightSession,
    *,
    company_name: str,
    linkedin_url: str | None = None,
    limit: int,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    jobs_url = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)["jobs_url"]
    if not await session.navigate(jobs_url, purpose="company_jobs"):
        return jobs
    try:
        jobs_data = await session.page.evaluate(
            """(limit) => {
            const results = [];
            const seen = new Set();
            for (const a of document.querySelectorAll('a[href*="/jobs/view/"]')) {
                let href = (a.href || '').split('?')[0];
                const id = href.match(/\\/jobs\\/view\\/(\\d{8,})/);
                if (!id) continue;
                const key = id[1];
                if (seen.has(key)) continue;
                seen.add(key);
                const title = (a.innerText || '').trim().split('\\n')[0];
                if (!title) continue;
                results.push({
                    job_title: title,
                    linkedin_url: 'https://www.linkedin.com/jobs/view/' + key + '/',
                });
                if (results.length >= limit) break;
            }
            return results;
        }""",
            limit,
        )
        for item in jobs_data or []:
            raw_title = (item.get("job_title") or "").strip()
            cleaned_title, location = _parse_job_title(raw_title, company_name)
            jobs.append(
                {
                    "job_title": cleaned_title,
                    "location": location,
                    "linkedin_url": item.get("linkedin_url"),
                    "source": "linkedin_playwright",
                }
            )
    except Exception:
        logger.debug("LinkedIn jobs scrape failed", exc_info=True)
    return jobs


async def fetch_employees_tavily(company_name: str, *, limit: int) -> list[dict[str, Any]]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key or limit <= 0:
        return []
    slug = company_name_to_slug(company_name)
    employees: list[dict[str, Any]] = []
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        for role_query in _EMPLOYEE_ROLE_QUERIES:
            if len(employees) >= limit:
                break
            remaining = limit - len(employees)
            batch_size = min(max(remaining, 5), 20)
            query = (
                f'site:linkedin.com/in "{company_name}" '
                + (f'"{slug}" ' if slug else "")
                + f"({role_query})"
            )
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=batch_size,
                count_as_linkedin=True,
            )
            batch: list[dict[str, Any]] = []
            for item in (response or {}).get("results") or []:
                url = item.get("url") or ""
                match = LINKEDIN_IN_RE.search(url)
                if not match:
                    continue
                profile_url = f"https://www.linkedin.com/in/{match.group(1)}/"
                title = (item.get("title") or "").strip()
                name = title.split(" - ")[0].split(" | ")[0].strip() if title else match.group(1)
                batch.append(
                    {
                        "name": name,
                        "designation": item.get("content", "")[:120] or None,
                        "linkedin_url": profile_url,
                        "source": "linkedin_tavily",
                    }
                )
            employees = _merge_employees(employees, batch, limit=limit)
    except Exception as exc:
        if not is_tavily_unreachable_error(exc):
            logger.warning("Tavily employee search failed: %s", exc)
    return employees[:limit]


async def fetch_jobs_tavily(company_name: str, *, limit: int) -> list[dict[str, Any]]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key or limit <= 0:
        return []
    slug = company_name_to_slug(company_name)
    query = (
        f'site:linkedin.com/jobs/view "{company_name}"'
        + (f' "{slug}"' if slug else "")
    )
    jobs: list[dict[str, Any]] = []
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = tavily_search_with_retry(
            client,
            query=query,
            search_depth="advanced",
            max_results=max(limit * 3, limit),
            count_as_linkedin=True,
        )
        seen: set[str] = set()
        for item in (response or {}).get("results") or []:
            url = item.get("url") or ""
            match = LINKEDIN_JOB_RE.search(url)
            if not match:
                continue
            job_id = match.group(1)
            if len(job_id) < 8:
                continue
            job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
            if job_url in seen:
                continue

            raw_title = (item.get("title") or "").strip()
            content = (item.get("content") or "").strip()
            if _looks_like_job_listicle(content):
                continue
            if not _mentions_company(company_name, raw_title, content, url):
                continue

            cleaned_title, location = _parse_job_title(raw_title or "Open role", company_name)
            seen.add(job_url)
            jobs.append(
                {
                    "job_title": cleaned_title,
                    "location": location,
                    "linkedin_url": job_url,
                    "snippet": content[:300] if content else None,
                    "source": "linkedin_tavily",
                }
            )
            if len(jobs) >= limit:
                break
    except Exception as exc:
        if not is_tavily_unreachable_error(exc):
            logger.warning("Tavily job search failed: %s", exc)
    return jobs[:limit]


def build_hiring_signals(jobs: list[dict[str, Any]]) -> list[str]:
    return [job.get("job_title") for job in jobs if job.get("job_title")]
