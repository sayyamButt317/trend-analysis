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

# Strict C-suite / founding leadership — not ICs or mid-level managers.
_C_LEVEL_TITLE_RE = re.compile(
    r"(?:"
    r"\b(?:ceo|cto|cfo|coo|cmo|cpo|cio|ciso|cro|chro)\b|"
    r"\bchief\s+(?:executive|technology|technical|financial|operating|operations|"
    r"marketing|product|information|revenue|human\s+resources)\b|"
    r"\b(?:co[\s-]?founder|cofounder|founder)\b|"
    r"\bmanaging\s+director\b|"
    r"\b(?:managing|founding|equity)\s+partner\b|"
    r"\bowner\b|"
    # "President" but not "Vice President"
    r"(?<!\bvice\s)\bpresident\b"
    r")",
    re.I,
)
# Roles that must never be treated as C-level even if a keyword partially matches.
_NOT_C_LEVEL_TITLE_RE = re.compile(
    r"\b("
    r"vice\s+president|\bvp\b|svp|avp|"
    r"hr\s+business\s+partner|business\s+partner|delivery\s+partner|"
    r"account\s+manager|project\s+manager|product\s+manager|engineering\s+manager|"
    r"software\s+engineer|founding\s+engineer|staff\s+engineer|principal\s+engineer|"
    r"full[\s-]?stack|backend\s+engineer|frontend\s+engineer|"
    r"engineer|developer|designer|analyst|consultant|specialist|"
    r"intern|trainee|executive\s+assistant|assistant\s+to|"
    r"recruiter|coordinator|associate\s+engineer"
    r")\b",
    re.I,
)
_TITLE_AS_NAME_RE = re.compile(
    r"^(chief|ceo|cto|cfo|coo|cmo|cpo|cio|ciso|founder|co[\s-]?founder|"
    r"managing\s+director|president|owner)\b",
    re.I,
)
_BLOG_DESIGNATION_RE = re.compile(
    r"(today[, ]+i('m| am)|excited to|transformative|discuss|#\s*\w|"
    r"##\s|consulting chief|beyond their)",
    re.I,
)
_KEYWORD_STUFFED_SLUG_RE = re.compile(
    r"(cto|cio|ceo|cfo|ciso|head-of-it|chief-technology)",
    re.I,
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


def is_c_level_title(title: str | None) -> bool:
    text = (title or "").strip()
    if not text:
        return False
    if not _C_LEVEL_TITLE_RE.search(text):
        return False
    # Reject IC / mid-level titles unless they also explicitly include founder/C-suite.
    if _NOT_C_LEVEL_TITLE_RE.search(text) and not re.search(
        r"\b(?:ceo|cto|cfo|coo|cmo|cpo|cio|ciso|cro|chro|founder|co[\s-]?founder|cofounder|"
        r"chief\s+(?:executive|technology|technical|financial|operating))\b",
        text,
        re.I,
    ):
        return False
    return True


def _pick_c_level_designation(lines: list[str] | None, fallback: str | None = None) -> str | None:
    """Choose the card line that looks like a real C-level title."""
    candidates = [ _clean_designation(line) for line in (lines or []) if line ]
    if fallback:
        candidates.append(_clean_designation(fallback))
    # Prefer an explicit C-level line over connection degree / company-only lines.
    for line in candidates[1:] if len(candidates) > 1 else candidates:
        if is_c_level_title(line):
            return line
    for line in candidates:
        if is_c_level_title(line):
            return line
    return candidates[1] if len(candidates) > 1 else (candidates[0] if candidates else None)


def _clean_designation(text: str | None) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    value = value.lstrip("#-• ").strip()
    if len(value) > 120:
        value = value[:117].rstrip() + "..."
    return value


def _looks_like_real_person_name(name: str | None) -> bool:
    text = (name or "").strip()
    if len(text) < 3 or len(text) > 80:
        return False
    if _TITLE_AS_NAME_RE.search(text):
        return False
    if re.search(r"[#@]|https?://", text):
        return False
    # Require at least one alphabetic token that isn't a job title word.
    tokens = [t for t in re.split(r"\s+", text) if t]
    if len(tokens) < 2:
        return False
    return True


def _looks_like_spam_profile(url: str | None, name: str | None, designation: str | None) -> bool:
    slug = ""
    match = LINKEDIN_IN_RE.search(url or "")
    if match:
        slug = match.group(1).lower()
    # SEO vanity URLs like /in/cto-cio-head-of-it-david-janak/
    title_hits = len(_KEYWORD_STUFFED_SLUG_RE.findall(slug))
    if title_hits >= 2:
        return True
    if _BLOG_DESIGNATION_RE.search(designation or ""):
        return True
    if _TITLE_AS_NAME_RE.search(name or ""):
        return True
    return False


def filter_c_level_employees(
    employees: list[dict[str, Any]],
    *,
    company_name: str | None = None,
    require_company: bool = True,
) -> list[dict[str, Any]]:
    """Keep only C-suite profiles that clearly belong to the company."""
    filtered: list[dict[str, Any]] = []
    for item in employees or []:
        name = (item.get("name") or "").strip()
        designation = _clean_designation(item.get("designation") or item.get("title"))
        url = item.get("linkedin_url") or ""
        evidence = item.get("evidence") or item.get("content") or ""
        if not _looks_like_real_person_name(name):
            continue
        if not is_c_level_title(designation):
            continue
        if _looks_like_spam_profile(url, name, designation):
            continue
        if require_company and company_name:
            # Title, snippet, or URL slug must mention the company (not random CTOs).
            if not _mentions_company(company_name, designation, name, url, str(evidence)):
                continue
        filtered.append(
            {
                **item,
                "name": name,
                "designation": designation or None,
                "title": designation or None,
                "level": "c_level",
            }
        )
    return filtered


_FOUNDERS_FROM_TEXT_RE = re.compile(
    r"(?:founded(?:\s+(?:in\s+)?\d{4})?\s+by|co[\s-]?founders?\s*[:\-]|founders?\s*[:\-])\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
    r"(?:\s*(?:,|\band\b|&)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}))?",
)


def extract_founders_from_text(
    text: str | None,
    *,
    company_name: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Pull founder names from website/about copy when LinkedIn people scrape is empty."""
    blob = (text or "").strip()
    if not blob:
        return []
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _FOUNDERS_FROM_TEXT_RE.finditer(blob):
        for group in match.groups():
            name = (group or "").strip(" .,;:")
            if not name or not _looks_like_real_person_name(name):
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "name": name,
                    "designation": "Founder",
                    "title": "Founder",
                    "linkedin_url": None,
                    "source": "website_text",
                    "level": "c_level",
                    "company": company_name,
                }
            )
            if len(found) >= limit:
                return found
    return found


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

_C_LEVEL_PEOPLE_KEYWORDS = (
    "CEO OR CTO OR CFO OR COO OR founder OR Chief",
)


async def scrape_employees_from_page(
    session: LinkedInPlaywrightSession,
    *,
    company_name: str,
    linkedin_url: str | None = None,
    limit: int,
) -> list[dict[str, Any]]:
    """Scrape company People page for C-level / founding profiles only."""
    employees: list[dict[str, Any]] = []
    base_people = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)["people_url"]
    # Keyword-filtered page first, then unfiltered people page as fallback.
    from urllib.parse import quote

    people_urls = [
        f"{base_people.rstrip('/')}?keywords={quote(kw)}"
        for kw in _C_LEVEL_PEOPLE_KEYWORDS
    ]
    people_urls.append(base_people)

    for people_url in people_urls:
        if len(employees) >= limit:
            break
        if not await session.navigate(people_url, purpose="company_employees"):
            continue
        try:
            await session.page.evaluate(
                """async (limit) => {
                const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
                let last = 0;
                for (let i = 0; i < 8; i++) {
                    window.scrollBy(0, Math.max(600, window.innerHeight * 0.9));
                    await sleep(450);
                    const count = document.querySelectorAll('a[href*="/in/"]').length;
                    if (count >= limit || count === last) break;
                    last = count;
                }
            }""",
                max(limit * 3, 20),
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
                        lines,
                        designation: lines[1] || null,
                        title: lines[1] || null,
                        linkedin_url: href,
                    });
                    if (results.length >= limit) break;
                }
                return results;
            }""",
                max(limit * 4, 30),
            )
            batch = []
            for item in (people_data or []):
                designation = _pick_c_level_designation(
                    item.get("lines") or [],
                    fallback=item.get("designation") or item.get("title"),
                )
                batch.append(
                    {
                        "name": item.get("name"),
                        "designation": designation,
                        "title": designation,
                        "linkedin_url": item.get("linkedin_url"),
                        "source": "linkedin_playwright",
                    }
                )
            employees = merge_employees(
                employees,
                filter_c_level_employees(
                    batch,
                    company_name=company_name,
                    # Already on this company's People page.
                    require_company=False,
                ),
                limit=limit,
            )
        except Exception:
            logger.debug("LinkedIn people scrape failed for %s", people_url, exc_info=True)
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
    """Find up to `limit` C-level LinkedIn profiles that belong to this company."""
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key or limit <= 0:
        return []
    slug = company_name_to_slug(company_name)
    employees: list[dict[str, Any]] = []
    # One tight query beats many broad CTO/CEO searches that pull unrelated people.
    queries = [
        (
            f'site:linkedin.com/in "{company_name}" '
            f'(CEO OR CTO OR CFO OR COO OR founder OR "Managing Director" OR "co-founder")'
        ),
        (
            f'site:linkedin.com/in "{company_name}" '
            + (f'"{slug}" ' if slug else "")
            + '(CEO OR CTO OR founder)'
        ),
    ]
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        for query in queries:
            if len(employees) >= limit:
                break
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=min(max(limit * 3, 6), 10),
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
                content = (item.get("content") or "").strip()
                # Typical: "Raheel Ahmed - Founder at Techtimize | LinkedIn"
                name = title.split(" - ")[0].split(" | ")[0].strip() if title else match.group(1)
                designation = None
                role_blob = ""
                if " - " in title:
                    role_blob = title.split(" - ", 1)[1]
                elif " | " in title:
                    role_blob = title.split(" | ", 1)[1]
                role_blob = role_blob.split(" | ")[0].strip()
                if role_blob:
                    # Strip trailing "at Company"
                    designation = re.sub(
                        r"\s+at\s+.+$",
                        "",
                        role_blob,
                        flags=re.I,
                    ).strip() or role_blob
                if not designation or not is_c_level_title(designation):
                    for line in content.split("\n"):
                        line = line.strip()
                        if is_c_level_title(line):
                            designation = _clean_designation(line)
                            break
                if not designation:
                    continue
                batch.append(
                    {
                        "name": name,
                        "designation": designation,
                        "title": designation,
                        "linkedin_url": profile_url,
                        "source": "linkedin_tavily",
                        "evidence": f"{title}\n{content[:400]}",
                    }
                )
            employees = _merge_employees(
                employees,
                filter_c_level_employees(
                    batch,
                    company_name=company_name,
                    require_company=True,
                ),
                limit=limit,
            )
    except Exception as exc:
        if not is_tavily_unreachable_error(exc):
            logger.warning("Tavily C-level employee search failed: %s", exc)
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
