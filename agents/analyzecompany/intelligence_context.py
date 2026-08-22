"""Shared helpers for company intelligence nodes (post-DNA insights)."""

from __future__ import annotations

from typing import Any


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                label = item.get("theme") or item.get("category") or item.get("name") or item.get("label")
                text = str(label or "").strip()
            else:
                text = str(item or "").strip()
            if text and text not in out:
                out.append(text)
        return out
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _clip(text: Any, limit: int = 220) -> str:
    value = " ".join(str(text or "").split()).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def intelligence_context(state: dict[str, Any]) -> dict[str, Any]:
    """Normalize DNA + social signals for scoring / insight nodes."""
    config = state.get("config") or {}
    summary = state.get("company_summary") or {}
    brief = dict(summary.get("brief") or {})
    company = dict(state.get("company_profile") or config.get("company") or {})
    analysis = dict(state.get("company_analysis") or {})
    dna = dict(analysis.get("company_dna") or {})
    website = dict(state.get("web_crawl") or analysis.get("website") or {})

    ig_wrap = analysis.get("user_instagram") or state.get("user_instagram") or {}
    ig = dict(analysis.get("instagram") or ig_wrap.get("instagram") or {})
    ig_profile = dict(ig_wrap.get("profile") or state.get("user_instagram_profile") or {})
    li_wrap = analysis.get("user_linkedin") or state.get("user_linkedin") or {}
    li = dict(
        li_wrap.get("linkedin_analysis")
        or li_wrap.get("analysis")
        or analysis.get("linkedin_analysis")
        or {}
    )

    services = _list(brief.get("services") or company.get("services") or dna.get("services"))
    flagship = _list(brief.get("flagship_services") or company.get("flagship_services") or services[:4])
    technologies = _list(brief.get("technologies") or company.get("technologies") or dna.get("technologies"))
    audience = _list(brief.get("target_audience") or company.get("target_audience") or dna.get("target_audience"))
    industries = _list(brief.get("industries_targeted") or dna.get("industries") or website.get("industries"))
    geography = _list(brief.get("geography") or [company.get("region"), company.get("country")])
    keywords = _list(brief.get("keywords") or company.get("keywords") or dna.get("keywords"))
    pain_points = _list(brief.get("pain_points") or company.get("pain_points") or dna.get("pain_points"))
    pricing = _list(brief.get("pricing_signals") or dna.get("pricing") or [company.get("pricing")])

    ig_followers = ig.get("followers")
    if ig_followers is None:
        ig_followers = ig_profile.get("followers_count")
    try:
        ig_followers = int(ig_followers) if ig_followers is not None else None
    except (TypeError, ValueError):
        ig_followers = None

    eng = ig.get("avg_engagement_rate")
    try:
        eng = float(eng) if eng is not None else None
    except (TypeError, ValueError):
        eng = None

    ig_analyzed = bool(
        config.get("user_instagram_analyzed")
        or ig
        or ig_profile
        or (brief.get("instagram") or {}).get("analyzed")
    )
    has_li_signal = bool(
        li_wrap.get("linkedin_posts")
        or analysis.get("linkedin_content_themes")
        or li.get("content_themes")
        or li
    )
    li_analyzed = bool(has_li_signal) and not bool(li_wrap.get("skipped"))

    website_crawled = bool(website.get("summary") or website.get("description") or website.get("services") or brief.get("website"))

    return {
        "config": config,
        "company": company,
        "brief": brief,
        "dna": dna,
        "website": website,
        "ig": ig,
        "ig_profile": ig_profile,
        "li": li,
        "li_wrap": li_wrap,
        "name": brief.get("name") or company.get("name") or "Company",
        "industry": brief.get("industry") or company.get("industry"),
        "region": brief.get("region") or company.get("region"),
        "services": services,
        "flagship": flagship,
        "technologies": technologies,
        "audience": audience,
        "industries": industries,
        "geography": geography,
        "keywords": keywords,
        "pain_points": pain_points,
        "pricing": pricing,
        "business_model": brief.get("business_model") or company.get("business_model") or dna.get("business_model"),
        "positioning": brief.get("positioning") or company.get("positioning") or dna.get("positioning"),
        "value_proposition": brief.get("value_proposition") or company.get("value_proposition"),
        "ig_followers": ig_followers,
        "ig_engagement": eng,
        "ig_themes": _list(ig.get("content_themes") or (brief.get("instagram") or {}).get("themes")),
        "ig_categories": _list(ig.get("content_categories") or (brief.get("instagram") or {}).get("categories")),
        "ig_analyzed": ig_analyzed,
        "li_analyzed": li_analyzed,
        "li_themes": _list(
            analysis.get("linkedin_content_themes")
            or li.get("content_themes")
            or (brief.get("linkedin") or {}).get("themes")
        ),
        "li_hiring": bool(analysis.get("is_hiring") or li.get("is_hiring") or li_wrap.get("is_hiring")),
        "website_crawled": website_crawled,
        "warnings": list(state.get("warnings") or []),
    }


def clamp_score(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))
