from __future__ import annotations
import logging
from typing import Any
from agents.competitor.state.competitor_state import CompetitorState

logger = logging.getLogger(__name__)


def apply_user_instagram_insights(
    config: dict[str, Any],
    *,
    username: str,
    profile: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    company = dict(config.get("company") or {})
    filters = dict(config.get("filters") or config)

    company.update(
        {
            "instagram_username": username,
            "instagram_url": f"https://www.instagram.com/{username}/",
            "name": profile.get("name") or company.get("name"),
            "bio": profile.get("biography") or profile.get("bio") or company.get("bio"),
            "website": profile.get("website") or company.get("website"),
        }
    )

    niche_keywords = analysis.get("niche_keywords") or []
    if niche_keywords:
        existing = list(filters.get("keywords") or [])
        for keyword in niche_keywords:
            if keyword and keyword not in existing:
                existing.append(keyword)
        filters["keywords"] = existing[:20]
        config["niche_keywords"] = niche_keywords

    detected = analysis.get("detected_niche") or analysis.get("primary_content_category")
    if detected:
        config["detected_category"] = detected
        config["detected_niche"] = detected
        filters["industry"] = filters.get("industry") or detected
        company["niche"] = detected

    exclude = list(filters.get("exclude_usernames") or [])
    if username.lower() not in {item.lower().lstrip("@") for item in exclude}:
        exclude.append(username.lower())
    filters["exclude_usernames"] = exclude

    signals = dict(config.get("company_signals") or {})
    signals["instagram_username"] = username
    signals["keywords"] = list(dict.fromkeys([*(signals.get("keywords") or []), *niche_keywords]))[:20]
    if detected:
        signals["flagship_services"] = list(
            dict.fromkeys([*(signals.get("flagship_services") or []), detected])
        )[:5]

    config["company"] = company
    config["company_username"] = username
    config["company_signals"] = signals
    config["filters"] = filters
    config["user_instagram_analyzed"] = True
    return config


def apply_user_linkedin_insights(
    config: dict[str, Any],
    *,
    linkedin_url: str,
    analysis: dict[str, Any] | None,
    posts: list[dict[str, Any]],
) -> dict[str, Any]:
    company = dict(config.get("company") or {})
    filters = dict(config.get("filters") or config)

    company["linkedin_url"] = linkedin_url
    themes = (analysis or {}).get("content_themes") or []
    theme_labels = [item.get("theme") for item in themes if isinstance(item, dict) and item.get("theme")]

    if theme_labels:
        existing = list(filters.get("keywords") or [])
        for label in theme_labels:
            if label and label not in existing:
                existing.append(str(label))
        filters["keywords"] = existing[:20]

    signals = dict(config.get("company_signals") or {})
    signals["linkedin_url"] = linkedin_url
    if theme_labels:
        signals["keywords"] = list(dict.fromkeys([*(signals.get("keywords") or []), *theme_labels]))[:20]

    config["company"] = company
    config["company_signals"] = signals
    config["filters"] = filters
    config["user_linkedin_analyzed"] = bool(posts or analysis)
    return config


def merge_company_analysis(state: CompetitorState, patch: dict[str, Any]) -> None:
    current = dict(state.get("company_analysis") or {})
    current.update(patch)
    state["company_analysis"] = current


def enrich_company_profile_for_discovery(state: CompetitorState) -> None:
    config = state.get("config") or {}
    company = config.get("company") or {}
    signals = config.get("company_signals") or {}
    profile = dict(state.get("company_profile") or {})

    profile.update(
        {
            "instagram_username": company.get("instagram_username"),
            "linkedin_url": company.get("linkedin_url"),
            "niche": profile.get("niche") or config.get("detected_niche") or company.get("niche"),
            "keywords": list(
                dict.fromkeys(
                    [
                        *(profile.get("keywords") or []),
                        *(signals.get("keywords") or []),
                        *(config.get("niche_keywords") or []),
                        *((config.get("filters") or {}).get("keywords") or []),
                    ]
                )
            )[:25],
        }
    )
    state["company_profile"] = profile
