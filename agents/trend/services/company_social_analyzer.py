import asyncio
import json
import logging
import re
from typing import Any

import httpx

from agents.trend.services.company_profile_parser import extract_social_handles, parse_company_profile
from agents.trend.services.content_analyzer import (
    classify_content_category,
    enrich_content_insights,
    normalize_media_type,
)
from agents.trend.services.instagram_discovery import fetch_instagram_profile
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


def _normalize_linkedin_company_url(url_or_slug: str) -> str | None:
    value = (url_or_slug or "").strip().rstrip("/")
    if not value:
        return None
    if "linkedin.com" in value:
        if "/company/" in value or "/in/" in value:
            return value if value.startswith("http") else f"https://www.{value.lstrip('www.')}"
        return None
    return f"https://www.linkedin.com/company/{value}/"


async def _resolve_handles_via_tavily(
    company_name: str,
    region: str | None,
    *,
    existing: dict[str, str | None],
) -> dict[str, str | None]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return existing

    from tavily import TavilyClient

    region_suffix = f" {region}" if region else ""
    queries: list[tuple[str, str]] = []
    if not existing.get("instagram_username"):
        queries.append(("instagram", f'{company_name}{region_suffix} official instagram account site:instagram.com'))
    if not existing.get("linkedin_url"):
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
                elif platform == "linkedin" and "/company/" in url:
                    resolved["linkedin_url"] = _normalize_linkedin_company_url(url)
                    match = re.search(r"/company/([^/?#]+)", url, re.I)
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
) -> dict[str, str | None]:
    profile_text = company.get("profile") or company.get("description") or ""
    handles = extract_social_handles(profile_text)
    handles["instagram_username"] = handles.get("instagram_username") or company.get("instagram_username")
    handles["instagram_url"] = handles.get("instagram_url") or company.get("instagram_url")
    handles["linkedin_url"] = _normalize_linkedin_company_url(
        handles.get("linkedin_url") or company.get("linkedin_url") or company.get("linkedin_username") or ""
    )
    handles["linkedin_username"] = handles.get("linkedin_username") or company.get("linkedin_username")

    company_name = (company.get("name") or "").strip()
    if company_name and (not handles.get("instagram_username") or not handles.get("linkedin_url")):
        handles = await _resolve_handles_via_tavily(company_name, region, existing=handles)
    return handles


def _heuristic_pain_points(texts: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
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
            if not any(re.search(pattern, clean, re.I) for pattern in PAIN_POINT_PATTERNS):
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            pain_points.append(
                {
                    "pain_point": clean,
                    "source": "linkedin_heuristic",
                    "confidence": "medium",
                }
            )
            if len(pain_points) >= limit:
                return pain_points
    return pain_points


async def _llm_pain_points(
    *,
    company_name: str,
    linkedin_posts: list[dict[str, Any]],
    company_signals: dict[str, Any],
) -> dict[str, Any]:
    api_key = (config.OPENAI_API_KEY or "").strip()
    model = (config.OPENAI_MODEL_NAME or "gpt-4o-mini").strip()
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


async def _fetch_linkedin_posts_tavily(
    linkedin_url: str,
    company_name: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return []

    from tavily import TavilyClient

    posts: list[dict[str, Any]] = []
    try:
        client = TavilyClient(api_key=api_key)
        if hasattr(client, "extract"):
            extract_result = client.extract(urls=[linkedin_url.rstrip("/") + "/posts/"])
            for chunk in extract_result.get("results") or []:
                content = chunk.get("raw_content") or chunk.get("content") or ""
                if content and len(content) > 100:
                    posts.append(
                        {
                            "text": content[:2000],
                            "source": "linkedin_extract",
                            "linkedin_url": linkedin_url,
                        }
                    )

        response = tavily_search_with_retry(
            client,
            query=f'site:linkedin.com/posts OR site:linkedin.com/feed "{company_name}"',
            search_depth="advanced",
            max_results=limit,
        )
        for item in (response or {}).get("results") or []:
            content = item.get("content") or item.get("raw_content") or ""
            if not content or len(content) < 60:
                continue
            posts.append(
                {
                    "text": content[:1500],
                    "title": item.get("title"),
                    "linkedin_url": item.get("url") or linkedin_url,
                    "source": "linkedin_tavily",
                }
            )
    except Exception as exc:
        if not is_tavily_unreachable_error(exc):
            logger.warning("LinkedIn Tavily fetch failed: %s", exc)
    return posts[:limit]


async def _fetch_linkedin_posts_playwright(linkedin_url: str, *, limit: int = 10) -> list[dict[str, Any]]:
    email, password = None, None
    try:
        from core.auth import load_credentials_from_env, login_with_credentials
        from core.browser import BrowserManager

        email, password = load_credentials_from_env()
        if not email or not password:
            return []
    except ImportError:
        return []

    posts: list[dict[str, Any]] = []
    try:
        async with BrowserManager(headless=True) as browser:
            await login_with_credentials(browser.page, email, password)
            posts_url = linkedin_url.rstrip("/") + "/posts/"
            await browser.page.goto(posts_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            posts_data = await browser.page.evaluate(
                """() => {
                const results = [];
                const html = document.body.innerHTML;
                const urnMatches = [...html.matchAll(/urn:li:activity:(\\d+)/g)];
                const seen = new Set();
                for (const match of urnMatches) {
                    const urn = match[0];
                    if (seen.has(urn)) continue;
                    seen.add(urn);
                    const el = document.querySelector(`[data-urn="${urn}"]`);
                    const text = el ? (el.innerText || '').trim() : '';
                    if (text && text.length > 30) {
                        results.push({ urn, text: text.slice(0, 1500) });
                    }
                    if (results.length >= 10) break;
                }
                return results;
            }"""
            )
            for item in posts_data or []:
                posts.append(
                    {
                        "text": item.get("text"),
                        "urn": item.get("urn"),
                        "linkedin_url": posts_url,
                        "source": "linkedin_playwright",
                    }
                )
    except Exception:
        logger.debug("LinkedIn Playwright fetch unavailable", exc_info=True)
    return posts[:limit]


async def fetch_linkedin_company_posts(
    linkedin_url: str,
    company_name: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    normalized = _normalize_linkedin_company_url(linkedin_url)
    if not normalized:
        return []

    posts = await _fetch_linkedin_posts_playwright(normalized, limit=limit)
    if not posts:
        posts = await _fetch_linkedin_posts_tavily(normalized, company_name, limit=limit)
    return posts


def analyze_instagram_company_profile(profile: dict[str, Any], posts: list[dict[str, Any]]) -> dict[str, Any]:
    insights = enrich_content_insights(posts, profile)
    hashtags: list[str] = []
    for post in posts:
        for tag in post.get("hashtags") or []:
            if isinstance(tag, dict):
                hashtags.append(tag.get("tag") or tag.get("hashtag") or "")
            else:
                hashtags.append(str(tag))

    from collections import Counter

    tag_counts = Counter(tag for tag in hashtags if tag)
    media_counts = Counter(normalize_media_type(post) for post in posts)
    categories = Counter(
        classify_content_category(post.get("caption") or post.get("text") or "", post.get("hashtags"))
        for post in posts
    )

    bio = profile.get("biography") or profile.get("bio") or ""
    focus_parts = (insights.get("content_focus") or "").split(", ") if insights.get("content_focus") else []
    niche_keywords = list(
        dict.fromkeys(
            [
                *focus_parts,
                categories.most_common(1)[0][0] if categories else "",
                profile.get("category") or "",
            ]
        )
    )
    niche_keywords = [item for item in niche_keywords if item and item != "General Brand"]

    return {
        "username": profile.get("username"),
        "name": profile.get("name"),
        "bio": bio,
        "followers": profile.get("followers_count"),
        "website": profile.get("website"),
        "post_count": len(posts),
        "primary_format": insights.get("primary_format"),
        "primary_content_category": insights.get("primary_content_category"),
        "content_focus": insights.get("content_focus"),
        "top_hashtags": [{"tag": tag, "count": count} for tag, count in tag_counts.most_common(10)],
        "media_mix": [{"format": fmt, "count": count} for fmt, count in media_counts.most_common()],
        "content_categories": [{"category": cat, "count": count} for cat, count in categories.most_common(5)],
        "posting_frequency": insights.get("posting_frequency") or {},
        "avg_engagement_rate": insights.get("avg_engagement_rate"),
        "detected_niche": niche_keywords[0] if niche_keywords else insights.get("primary_content_category"),
        "niche_keywords": niche_keywords[:8],
        "caption_style": insights.get("caption_style") or {},
    }


async def analyze_company_social_presence(
    company: dict[str, Any],
    *,
    region: str | None = None,
    post_limit: int = 15,
) -> dict[str, Any]:
    company_name = (company.get("name") or "").strip() or "Company"
    signals = company.get("company_signals")
    if not signals:
        signals = parse_company_profile(company.get("profile") or "", company=company).to_dict()

    handles = await resolve_company_social_handles(company, region=region)
    warnings: list[str] = []

    instagram_username = handles.get("instagram_username")
    linkedin_url = handles.get("linkedin_url")

    instagram_profile: dict[str, Any] | None = None
    instagram_posts: list[dict[str, Any]] = []
    instagram_analysis: dict[str, Any] | None = None

    if instagram_username:
        profile = await fetch_instagram_profile(instagram_username, post_limit=post_limit)
        if profile:
            instagram_profile = profile
            instagram_posts = profile.get("posts") or []
            for post in instagram_posts:
                post["username"] = instagram_username
                post["is_company_post"] = True
            instagram_analysis = analyze_instagram_company_profile(profile, instagram_posts)
        else:
            warnings.append(f"Could not fetch Instagram profile for @{instagram_username}.")
    else:
        warnings.append("No Instagram username found in company data.")

    linkedin_posts: list[dict[str, Any]] = []
    if linkedin_url:
        linkedin_posts = await fetch_linkedin_company_posts(
            linkedin_url,
            company_name,
            limit=min(post_limit, 10),
        )
        if not linkedin_posts:
            warnings.append(f"Could not fetch LinkedIn posts from {linkedin_url}.")
    else:
        warnings.append("No LinkedIn company URL found in company data.")

    post_texts = [post.get("text") or "" for post in linkedin_posts if post.get("text")]
    heuristic_pain_points = _heuristic_pain_points(post_texts)
    llm_result = await _llm_pain_points(
        company_name=company_name,
        linkedin_posts=linkedin_posts,
        company_signals=signals if isinstance(signals, dict) else {},
    )
    if isinstance(llm_result, dict):
        pain_points = llm_result.get("pain_points") or heuristic_pain_points
        audience_needs = llm_result.get("audience_needs") or []
        linkedin_themes = llm_result.get("content_themes") or []
    else:
        pain_points = heuristic_pain_points
        audience_needs = []
        linkedin_themes = []

    if not pain_points and linkedin_posts:
        pain_points = heuristic_pain_points

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
        "pain_points": pain_points,
        "audience_needs": audience_needs,
        "detected_niche": detected_category,
        "detected_category": detected_category,
        "company_signals": signals,
        "warnings": warnings,
    }
