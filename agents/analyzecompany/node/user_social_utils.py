"""Social insight helpers — Instagram/LinkedIn are GTM signals, not DNA sources."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def apply_user_instagram_insights(
    config: dict[str, Any],
    *,
    username: str,
    profile: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """Attach Instagram identity + content signals only.

    Do not overwrite website DNA (technologies, niche, industry, business model, services).
    """
    company = dict(config.get("company") or {})
    filters = dict(config.get("filters") or config)

    company.update(
        {
            "instagram_username": username,
            "instagram_url": f"https://www.instagram.com/{username}/",
            "name": company.get("name") or profile.get("name"),
            "bio": profile.get("biography") or profile.get("bio") or company.get("bio"),
            # Only fill website if still missing (crawl may have failed).
            "website": company.get("website") or profile.get("website"),
        }
    )

    exclude = list(filters.get("exclude_usernames") or [])
    if username.lower() not in {item.lower().lstrip("@") for item in exclude}:
        exclude.append(username.lower())
    filters["exclude_usernames"] = exclude

    signals = dict(config.get("company_signals") or {})
    signals["instagram_username"] = username
    # Content-only signals for GTM / pain inference — not DNA fields.
    signals["instagram_content_themes"] = analysis.get("content_themes") or []
    signals["instagram_content_categories"] = analysis.get("content_categories") or []
    signals["instagram_bio"] = profile.get("biography") or profile.get("bio")

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
    """Attach LinkedIn URL + content themes only — do not overwrite website DNA."""
    company = dict(config.get("company") or {})
    filters = dict(config.get("filters") or config)

    company["linkedin_url"] = linkedin_url
    themes = (analysis or {}).get("content_themes") or []
    theme_labels = [
        item.get("theme") for item in themes if isinstance(item, dict) and item.get("theme")
    ]

    signals = dict(config.get("company_signals") or {})
    signals["linkedin_url"] = linkedin_url
    if theme_labels:
        signals["linkedin_content_themes"] = theme_labels
    specialties = _list((analysis or {}).get("specialties"))
    if specialties and not (company.get("website") or config.get("company_website")):
        # LinkedIn fallback only when no website DNA exists.
        signals["linkedin_specialties"] = specialties

    config["company"] = company
    config["company_signals"] = signals
    config["filters"] = filters
    config["user_linkedin_analyzed"] = bool(posts or analysis)
    return config


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def merge_company_analysis(state: dict[str, Any], patch: dict[str, Any]) -> None:
    current = dict(state.get("company_analysis") or {})
    current.update(patch)
    state["company_analysis"] = current


def enrich_company_profile_for_discovery(state: dict[str, Any]) -> None:
    """Keep social handles on profile; do not merge IG niche into company DNA keywords."""
    config = state.get("config") or {}
    company = config.get("company") or {}
    profile = dict(state.get("company_profile") or {})

    profile.update(
        {
            "instagram_username": company.get("instagram_username"),
            "linkedin_url": company.get("linkedin_url"),
            # Prefer website/company niche — never Instagram content category.
            "niche": company.get("industry") or company.get("niche") or profile.get("niche"),
            "keywords": list(dict.fromkeys(profile.get("keywords") or company.get("keywords") or []))[:25],
        }
    )
    state["company_profile"] = profile
