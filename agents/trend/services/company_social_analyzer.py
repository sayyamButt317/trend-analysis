import asyncio
import json
import logging
import re
from typing import Any
import httpx

from agents.trend.services.company_profile_parser import extract_social_handles, parse_company_profile
from service.AnalyzeUserInstagram.contentstrategy import build_instagram_analysis
from service.AnalyzeUserInstagram.fetchprofile import fetch_user_instagram_profile, posts_from_profile
from service.AnalyzeUserLinkedIn import fetch_linkedin_company_posts as _fetch_linkedin_company_posts
from service.AnalyzeUserLinkedIn import normalize_linkedin_url
from config.credential_config import config
from scrapper.instagram_finder.extractor import extract_username
from scrapper.tavily_retry import is_tavily_unreachable_error, tavily_search_with_retry

logger = logging.getLogger(__name__)

PAIN_POINT_PATTERNS = (
    r"\b(challenge[ds]?|struggl(?:e|ing|es)|pain point[s]?|problem[s]?|frustrat(?:ed|ion|ing))\b",
    r"\b(need[s]? help|looking for|searching for|hard to|difficult to|lack of|bottleneck)\b",
    r"\b(can't|cannot|unable to|fail(?:ed|ing|ure)? to|issue[s]? with|barrier[s]?)\b",
    r"\b(cost[s]? too much|too expensive|time.?consuming|inefficien(?:t|cy)|manual process)\b",
)

COMPANY_SELF_PATTERNS = (
    r"\b(we are hiring|we're hiring|join our team|our office|our culture|we're excited)\b",
    r"\b(proud to announce|we announce|follow us|dm us|book a call with us)\b",
    r"\b(our new office|our anniversary|we won an award|we're expanding our team)\b",
)

AUDIENCE_SIGNAL_PATTERNS = (
    r"\b(clients?|customers?|users?|businesses|teams|founders|marketers|brands)\b",
    r"\b(many companies|most teams|agencies|startups|enterprises|smb[s]?)\b",
    r"\b(their|they struggle|they face|they need|audience|buyers?)\b",
    r"\b(you struggle|you face|you need|your business|your team)\b",
)


LINKEDIN_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w.]+)\.?linkedin\.com/(company|in)/([A-Za-z0-9_-]+)/?",
    re.I,
)


def _normalize_linkedin_url(url_or_slug: str) -> str | None:
    return normalize_linkedin_url(url_or_slug)


def _linkedin_posts_path(linkedin_url: str) -> str:
    from service.AnalyzeUserLinkedIn import linkedin_posts_path

    return linkedin_posts_path(linkedin_url)


async def _resolve_handles_via_tavily(
    company_name: str,
    region: str | None,
    *,
    existing: dict[str, str | None],
    resolve_linkedin: bool = True,
) -> dict[str, str | None]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return existing

    from tavily import TavilyClient

    region_suffix = f" {region}" if region else ""
    queries: list[tuple[str, str]] = []
    if not existing.get("instagram_username"):
        queries.append(("instagram", f'{company_name}{region_suffix} official instagram account site:instagram.com'))
    if resolve_linkedin and not existing.get("linkedin_url"):
        queries.append(("linkedin", f'{company_name}{region_suffix} linkedin company page site:linkedin.com/company'))

    resolved = dict(existing)
    try:
        client = TavilyClient(api_key=api_key)
        for platform, query in queries:
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=5,
                count_as_linkedin=(platform == "linkedin"),
            )
            if not response:
                continue
            for item in response.get("results") or []:
                url = item.get("url") or ""
                if platform == "instagram":
                    username = extract_username(url)
                    if username:
                        resolved["instagram_username"] = username
                        resolved["instagram_url"] = f"https://www.instagram.com/{username}/"
                        break
                elif platform == "linkedin" and ("/company/" in url or "/in/" in url):
                    resolved["linkedin_url"] = _normalize_linkedin_url(url)
                    match = re.search(r"/(?:company|in)/([^/?#]+)", url, re.I)
                    if match:
                        resolved["linkedin_username"] = match.group(1)
                    break
    except Exception as exc:
        if not is_tavily_unreachable_error(exc):
            logger.warning("Tavily social handle resolution failed: %s", exc)
    return resolved


async def resolve_company_social_handles(
    company: dict[str, Any],
    *,
    region: str | None = None,
    resolve_linkedin: bool = True,
) -> dict[str, str | None]:
    profile_text = company.get("profile") or company.get("description") or ""
    handles = extract_social_handles(profile_text)
    handles["instagram_username"] = handles.get("instagram_username") or company.get("instagram_username")
    handles["instagram_url"] = handles.get("instagram_url") or company.get("instagram_url")
    handles["linkedin_url"] = _normalize_linkedin_url(
        handles.get("linkedin_url") or company.get("linkedin_url") or company.get("linkedin_username") or ""
    )
    handles["linkedin_username"] = handles.get("linkedin_username") or company.get("linkedin_username")

    company_name = (company.get("name") or "").strip()
    needs_instagram = not handles.get("instagram_username")
    needs_linkedin = resolve_linkedin and not handles.get("linkedin_url")
    if company_name and (needs_instagram or needs_linkedin):
        handles = await _resolve_handles_via_tavily(
            company_name,
            region,
            existing=handles,
            resolve_linkedin=resolve_linkedin,
        )
    return handles


def _is_company_self_reference(text: str) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered, re.I) for pattern in COMPANY_SELF_PATTERNS)


def _has_audience_signal(text: str) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered, re.I) for pattern in AUDIENCE_SIGNAL_PATTERNS)


def _heuristic_audience_pain_points(texts: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
    pain_points: list[dict[str, Any]] = []
    seen: set[str] = set()
    for text in texts:
        if not text or len(text) < 40:
            continue
        lowered = text.lower()
        if not any(re.search(pattern, lowered, re.I) for pattern in PAIN_POINT_PATTERNS):
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            clean = sentence.strip()
            if len(clean) < 25 or len(clean) > 280:
                continue
            if _is_company_self_reference(clean):
                continue
            if not any(re.search(pattern, clean, re.I) for pattern in PAIN_POINT_PATTERNS):
                continue
            if not (_has_audience_signal(clean) or re.search(r"\b(you|your|clients?|customers?)\b", clean, re.I)):
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            pain_points.append(
                {
                    "pain_point": clean,
                    "source": "audience_heuristic",
                    "confidence": "medium",
                    "type": "audience_pain_point",
                }
            )
            if len(pain_points) >= limit:
                return pain_points
    return pain_points


async def _fetch_audience_pain_discussions(
    *,
    company_name: str,
    niche: str | None,
    services: list[str],
    region: str | None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return []

    from tavily import TavilyClient

    niche_label = niche or (services[0] if services else company_name)
    region_suffix = f" {region}" if region else ""
    queries = [
        f'site:linkedin.com/posts OR site:linkedin.com/pulse "{niche_label}" customer challenges pain points{region_suffix}',
        f'site:linkedin.com "{niche_label}" businesses struggle with problems{region_suffix}',
        f'site:reddit.com "{niche_label}" pain points challenges{region_suffix}',
    ]

    chunks: list[str] = []
    try:
        client = TavilyClient(api_key=api_key)
        for query in queries:
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=5,
            )
            for item in (response or {}).get("results") or []:
                content = item.get("content") or item.get("raw_content") or ""
                if content:
                    chunks.append(content)
    except Exception as exc:
        if not is_tavily_unreachable_error(exc):
            logger.warning("Audience pain discussion search failed: %s", exc)

    return _heuristic_audience_pain_points(chunks, limit=limit)


async def _llm_audience_pain_points(
    *,
    company_name: str,
    company_profile: str,
    linkedin_posts: list[dict[str, Any]],
    instagram_posts: list[dict[str, Any]],
    company_signals: dict[str, Any],
    niche: str | None = None,
) -> dict[str, Any]:
    api_key = (config.OPENAI_API_KEY or "").strip()
    model = (config.OPENAI_MODEL_NAME or "gpt-4o").strip()
    if not api_key:
        return {"pain_points": [], "audience_needs": [], "content_themes": []}

    services = company_signals.get("flagship_services") or company_signals.get("services") or []
    industries = company_signals.get("target_industries") or []
    linkedin_text = "\n\n".join(
        f"LinkedIn post {idx + 1}: {(post.get('text') or '')[:500]}"
        for idx, post in enumerate(linkedin_posts[:8])
    )
    instagram_text = "\n\n".join(
        f"Instagram post {idx + 1}: {(post.get('caption') or post.get('text') or '')[:400]}"
        for idx, post in enumerate(instagram_posts[:8])
    )
    prompt = f"""You analyze a company's public content to infer the pain points of their TARGET AUDIENCE (customers/clients), NOT the company's internal problems.

Company: {company_name}
Niche: {niche or "unknown"}
Services: {", ".join(services[:6])}
Target industries: {", ".join(industries[:6])}

Company profile:
{(company_profile or "")[:1200]}

LinkedIn posts (marketing/content from the company):
{linkedin_text or "None"}

Instagram posts:
{instagram_text or "None"}

Rules:
- Extract pain points faced by the company's CUSTOMERS / TARGET AUDIENCE only.
- Do NOT list the company's own hiring, culture, product launch, or internal operational issues.
- Infer audience pain from: problems the company says it solves, "you/your business" language, client stories, industry challenges discussed.
- Each pain_point should be a short audience problem statement (e.g. "Manual reporting wastes marketing team time").

Return ONLY JSON:
{{
  "audience_pain_points": [
    {{"pain_point": "audience problem", "evidence": "quote or paraphrase from content", "confidence": "high|medium|low"}}
  ],
  "audience_needs": ["what the target audience needs or wants"],
  "content_themes": ["themes in company social content"]
}}"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Extract audience/customer pain points only. "
                                "Never return the company's own internal pain points. Return only JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
        response.raise_for_status()
        data = json.loads(response.json()["choices"][0]["message"]["content"])
        points = []
        for item in data.get("audience_pain_points") or data.get("pain_points") or []:
            if item.get("pain_point"):
                points.append(
                    {
                        "pain_point": item["pain_point"],
                        "evidence": item.get("evidence"),
                        "confidence": item.get("confidence") or "medium",
                        "source": "audience_llm",
                        "type": "audience_pain_point",
                    }
                )
        return {
            "pain_points": points[:8],
            "audience_needs": data.get("audience_needs") or [],
            "content_themes": data.get("content_themes") or [],
        }
    except Exception:
        logger.exception("LLM audience pain point analysis failed")
        return {"pain_points": [], "audience_needs": [], "content_themes": []}


def _heuristic_pain_points(texts: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
    return _heuristic_audience_pain_points(texts, limit=limit)


async def _llm_pain_points(
    *,
    company_name: str,
    linkedin_posts: list[dict[str, Any]],
    company_signals: dict[str, Any],
) -> dict[str, Any]:
    api_key = (config.OPENAI_API_KEY or "").strip()
    model = (config.OPENAI_MODEL_NAME or "gpt-4o").strip()
    if not api_key or not linkedin_posts:
        return []

    post_text = "\n\n".join(
        f"Post {idx + 1}: {(post.get('text') or '')[:500]}"
        for idx, post in enumerate(linkedin_posts[:8])
    )
    prompt = f"""Analyze these LinkedIn posts from {company_name} and identify customer/business pain points they address or imply.

Services: {", ".join(company_signals.get("flagship_services") or company_signals.get("services") or [])[:5]}
Industries: {", ".join(company_signals.get("target_industries") or [])}

Posts:
{post_text}

Return ONLY JSON:
{{
  "pain_points": [
    {{"pain_point": "short description", "evidence": "quote or paraphrase from posts", "confidence": "high|medium|low"}}
  ],
  "audience_needs": ["what their audience likely needs"],
  "content_themes": ["main themes in their LinkedIn content"]
}}
"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "Return only JSON."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
        response.raise_for_status()
        data = json.loads(response.json()["choices"][0]["message"]["content"])
        points = []
        for item in data.get("pain_points") or []:
            if item.get("pain_point"):
                points.append(
                    {
                        "pain_point": item["pain_point"],
                        "evidence": item.get("evidence"),
                        "confidence": item.get("confidence") or "medium",
                        "source": "linkedin_llm",
                    }
                )
        return {
            "pain_points": points[:8],
            "audience_needs": data.get("audience_needs") or [],
            "content_themes": data.get("content_themes") or [],
        }
    except Exception:
        logger.exception("LLM pain point analysis failed")
        return {"pain_points": [], "audience_needs": [], "content_themes": []}


async def fetch_linkedin_company_posts(
    company_name: str,
    *,
    linkedin_url: str | None = None,
    limit: int = 10,
    skip_playwright: bool = False,
) -> list[dict[str, Any]]:
    return await _fetch_linkedin_company_posts(
        company_name,
        linkedin_url=linkedin_url,
        limit=limit,
        skip_playwright=skip_playwright,
    )


def analyze_instagram_company_profile(profile: dict[str, Any], posts: list[dict[str, Any]]) -> dict[str, Any]:
    return build_instagram_analysis(profile, posts)


async def analyze_company_social_presence(
    company: dict[str, Any],
    *,
    region: str | None = None,
    post_limit: int = 15,
    skip_discussion_search: bool = False,
    skip_playwright: bool = False,
) -> dict[str, Any]:
    company_name = (company.get("name") or "").strip() or "Company"
    signals = company.get("company_signals")
    if not signals:
        signals = parse_company_profile(company.get("profile") or "", company=company).to_dict()

    handles = await resolve_company_social_handles(company, region=region, resolve_linkedin=True)
    warnings: list[str] = []

    instagram_username = handles.get("instagram_username")
    linkedin_url = handles.get("linkedin_url")

    instagram_profile: dict[str, Any] | None = None
    instagram_posts: list[dict[str, Any]] = []
    instagram_analysis: dict[str, Any] | None = None

    if instagram_username:
        profile = await fetch_user_instagram_profile(instagram_username, post_limit=post_limit)
        if profile:
            instagram_profile = profile
            instagram_posts = posts_from_profile(profile, handle=instagram_username)
            for post in instagram_posts:
                post["username"] = instagram_username
                post["is_company_post"] = True
            instagram_analysis = analyze_instagram_company_profile(profile, instagram_posts)
        else:
            warnings.append(f"Could not fetch Instagram profile for @{instagram_username}.")
    else:
        warnings.append("No Instagram username found in company data.")

    linkedin_posts: list[dict[str, Any]] = []
    if company_name:
        linkedin_posts = await fetch_linkedin_company_posts(
            company_name,
            linkedin_url=linkedin_url,
            limit=min(post_limit, 10),
            skip_playwright=skip_playwright,
        )
        if not linkedin_posts:
            from service.AnalyzeUserLinkedIn import build_company_urls_from_name

            warnings.append(
                f"Could not fetch LinkedIn posts from {build_company_urls_from_name(company_name)['posts_url']}."
            )
    else:
        warnings.append("No company name found for LinkedIn analysis.")

    post_texts = [post.get("text") or "" for post in linkedin_posts if post.get("text")]
    instagram_texts = [
        post.get("caption") or post.get("text") or ""
        for post in instagram_posts
        if post.get("caption") or post.get("text")
    ]
    detected_niche = (instagram_analysis or {}).get("detected_niche") if instagram_analysis else None

    llm_result = await _llm_audience_pain_points(
        company_name=company_name,
        company_profile=company.get("profile") or company.get("description") or "",
        linkedin_posts=linkedin_posts,
        instagram_posts=instagram_posts,
        company_signals=signals if isinstance(signals, dict) else {},
        niche=detected_niche,
    )
    heuristic_from_content = _heuristic_audience_pain_points(
        post_texts + instagram_texts,
        limit=8,
    )
    discussion_pain_points: list[dict[str, Any]] = []
    if not skip_discussion_search:
        discussion_pain_points = await _fetch_audience_pain_discussions(
            company_name=company_name,
            niche=detected_niche,
            services=list(signals.get("flagship_services") or signals.get("services") or []) if isinstance(signals, dict) else [],
            region=region,
            limit=6,
        )

    if isinstance(llm_result, dict):
        pain_points = llm_result.get("pain_points") or []
        audience_needs = llm_result.get("audience_needs") or []
        linkedin_themes = llm_result.get("content_themes") or []
    else:
        pain_points = []
        audience_needs = []
        linkedin_themes = []

    if not pain_points:
        pain_points = heuristic_from_content
    if not pain_points:
        pain_points = discussion_pain_points

    # Merge unique audience pain points from all sources
    seen: set[str] = set()
    merged_pain_points: list[dict[str, Any]] = []
    for item in pain_points + heuristic_from_content + discussion_pain_points:
        key = (item.get("pain_point") or "").lower()
        if key and key not in seen:
            seen.add(key)
            merged_pain_points.append(item)
    pain_points = merged_pain_points[:10]

    detected_category = (
        instagram_analysis.get("detected_niche")
        if instagram_analysis
        else (signals.get("flagship_services") or signals.get("services") or [None])[0]
    )

    return {
        "company_name": company_name,
        "social_handles": handles,
        "instagram": instagram_analysis,
        "instagram_posts": instagram_posts,
        "linkedin_url": linkedin_url,
        "linkedin_posts": linkedin_posts,
        "linkedin_content_themes": linkedin_themes,
        "audience_pain_points": pain_points,
        "pain_points": pain_points,
        "audience_needs": audience_needs,
        "detected_niche": detected_category,
        "detected_category": detected_category,
        "company_signals": signals,
        "warnings": warnings,
    }
