import logging
import re
from collections import Counter
from typing import Any

from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.company_social_analyzer import (
    fetch_linkedin_company_posts,
    resolve_company_social_handles,
)
from agents.trend.services.content_analyzer import classify_content_category

logger = logging.getLogger(__name__)

Competitor = dict[str, Any]

LINKEDIN_THEME_PATTERNS = (
    r"\b(hiring|we're hiring|join our team|career)\b",
    r"\b(product launch|new feature|announcement|proud to)\b",
    r"\b(case study|client success|customer story)\b",
    r"\b(tips?|how to|guide|best practices?)\b",
    r"\b(industry trend|market|growth|innovation)\b",
)


def _extract_linkedin_themes(posts: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    theme_counts: Counter[str] = Counter()
    for post in posts:
        text = (post.get("text") or post.get("title") or "").lower()
        if not text:
            continue
        for pattern in LINKEDIN_THEME_PATTERNS:
            if re.search(pattern, text, re.I):
                theme_counts[pattern] += 1
        category = classify_content_category(text, [])
        if category and category != "General Brand":
            theme_counts[category] += 1
    return [{"theme": theme, "count": count} for theme, count in theme_counts.most_common(limit)]


def _summarize_linkedin_posts(posts: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [post.get("text") or post.get("title") or "" for post in posts if post.get("text") or post.get("title")]
    avg_len = round(sum(len(text) for text in texts) / len(texts)) if texts else 0
    return {
        "post_count": len(posts),
        "avg_post_length": avg_len,
        "content_themes": _extract_linkedin_themes(posts),
        "sample_posts": [
            {
                "text": (post.get("text") or post.get("title") or "")[:500],
                "source": post.get("source"),
                "linkedin_url": post.get("linkedin_url"),
            }
            for post in posts[:5]
        ],
    }


async def analyze_competitor_linkedin(
    competitor: Competitor,
    *,
    region: str | None = None,
    post_limit: int = 10,
    skip_playwright: bool = False,
) -> Competitor:
    """Resolve and analyze a competitor's LinkedIn company page."""
    name = (competitor.get("name") or competitor.get("username") or "").strip()
    linkedin_url = competitor.get("linkedin_url")
    warnings: list[str] = list(competitor.get("social_warnings") or [])

    if not linkedin_url and name:
        handles = await resolve_company_social_handles(
            {
                "name": name,
                "website": competitor.get("website"),
                "profile": competitor.get("bio") or "",
                "linkedin_url": competitor.get("linkedin_url"),
                "linkedin_username": competitor.get("linkedin_username"),
            },
            region=region,
        )
        linkedin_url = handles.get("linkedin_url")
        if handles.get("linkedin_username"):
            competitor["linkedin_username"] = handles["linkedin_username"]

    enriched = dict(competitor)
    if not linkedin_url:
        warnings.append(f"No LinkedIn company page found for '{name}'.")
        enriched["social_warnings"] = warnings
        enriched["linkedin_analysis"] = None
        return enriched

    posts = await fetch_linkedin_company_posts(
        linkedin_url,
        name,
        limit=post_limit,
        skip_playwright=skip_playwright,
    )
    if not posts:
        warnings.append(f"Could not fetch LinkedIn posts from {linkedin_url}.")

    analysis = _summarize_linkedin_posts(posts)
    enriched.update(
        {
            "linkedin_url": linkedin_url,
            "linkedin_posts": posts,
            "linkedin_analysis": analysis,
            "social_warnings": warnings,
        }
    )
    return enriched


async def analyzeCompetitorLinkedin(competitor: Competitor) -> Competitor:
    return await analyze_competitor_linkedin(competitor)


async def AnalyzeCompetitorLinkedinNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    if config.get("skip_linkedin"):
        logger.info("Skipping LinkedIn analysis (serverless mode)")
        return state

    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")
    post_limit = min(int(filters.get("post_limit") or config.get("post_limit") or 15), 10)
    skip_playwright = bool(config.get("skip_playwright"))

    competitors = state.get("discovered_influencers") or state.get("competitors") or []
    enriched: list[Competitor] = []

    for competitor in competitors:
        try:
            item = await analyze_competitor_linkedin(
                competitor,
                region=region,
                post_limit=post_limit,
                skip_playwright=skip_playwright,
            )
            enriched.append(item)
        except Exception:
            logger.exception(
                "LinkedIn analysis failed for competitor=%s",
                competitor.get("username") or competitor.get("name"),
            )
            enriched.append({**competitor, "linkedin_analysis": None})

    state["discovered_influencers"] = enriched
    state["competitors"] = enriched
    return state
