from __future__ import annotations
import logging
import re
from typing import Any
from service.Competitor.competitor_name_filters import is_junk_competitor
from service.Competitor.platforms import filter_competitor_socials

logger = logging.getLogger(__name__)

IG_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{2,30}$")
LINKEDIN_COMPANY_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/company/[A-Za-z0-9\-_%]+/?",
    re.I,
)
MIN_COMPETITORS = 10


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                label = item.get("name") or item.get("label") or item.get("text")
                if label:
                    out.append(str(label).strip())
        return out
    return []


def _normalize_instagram(raw: Any) -> str | None:
    if not raw:
        return None
    handle = str(raw).strip().lstrip("@").split("/")[-1].split("?")[0].strip().lower()
    if not handle or handle in {"instagram.com", "www.instagram.com", "p", "reel", "reels"}:
        return None
    if not IG_HANDLE_RE.match(handle):
        return None
    return handle


def _normalize_linkedin(raw: Any) -> str | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.startswith("company/"):
        text = f"https://www.linkedin.com/{text}"
    if "linkedin.com" not in text.lower() and "/" not in text:
        text = f"https://www.linkedin.com/company/{text.strip('/')}/"
    match = LINKEDIN_COMPANY_RE.search(text)
    if not match:
        return None
    url = match.group(0)
    if not url.endswith("/"):
        url = f"{url}/"
    return url


def _build_user_dna_blob(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any],
    company_signals: dict[str, Any] | None = None,
    discovery_features: dict[str, Any] | None = None,
    instagram_analysis: dict[str, Any] | None = None,
    linkedin_analysis: dict[str, Any] | None = None,
    website_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dna = company_analysis.get("company_dna") or {}
    company_signals = company_signals or {}
    discovery_features = discovery_features or {}
    instagram_analysis = instagram_analysis or {}
    linkedin_analysis = linkedin_analysis or {}
    website_intelligence = website_intelligence or {}

    user_ig = (company_analysis.get("user_instagram") or {}).get("instagram") or {}
    user_li = (company_analysis.get("user_linkedin") or {}).get("linkedin") or {}

    services = (
        _as_list(dna.get("services"))
        or _as_list(company_profile.get("services"))
        or _as_list(company.get("services"))
        or _as_list(company.get("flagship_services"))
    )
    technologies = (
        _as_list(dna.get("technologies"))
        or _as_list(company_profile.get("technologies"))
        or _as_list((company.get("extracted_signals") or {}).get("technologies"))
    )
    keywords = (
        _as_list(dna.get("keywords"))
        or _as_list(company_profile.get("keywords"))
        or _as_list(company.get("extracted_keywords"))
    )

    return {
        "name": company.get("name") or company_profile.get("name"),
        "website": company.get("website") or company_profile.get("website"),
        "instagram_username": (
            company.get("instagram_username")
            or user_ig.get("username")
        ),
        "linkedin_url": company.get("linkedin_url"),
        "services": (
            company_signals.get("services")
            or services
        )[:25],

        "flagship_services": (
            company_signals.get("flagship_services")
            or _as_list(company.get("flagship_services"))
        )[:10],

        "technologies": (
            company_signals.get("technologies")
            or technologies
        )[:25],

        "keywords": (
            company_signals.get("keywords")
            or keywords
        )[:30],

        "target_audience": (
            company_signals.get("target_industries")
            or _as_list(
                dna.get("target_audience")
                or company_profile.get("target_audience")
            )
        )[:20],

        "positioning": (
            dna.get("positioning")
            or company_profile.get("positioning")
        ),

        "value_proposition": (
            dna.get("value_proposition")
            or company_profile.get("value_proposition")
        ),

        # --------------------------------------------------
        # Website Intelligence
        # --------------------------------------------------
        "website_summary": (
            website_intelligence.get("summary")
            or ""
        )[:1000],

        "website_services": (
            website_intelligence.get("services")
            or []
        )[:20],

        "website_industries": (
            website_intelligence.get("industries")
            or []
        )[:20],

        "website_technologies": (
            website_intelligence.get("technologies")
            or []
        )[:20],

        # --------------------------------------------------
        # Instagram Intelligence
        # --------------------------------------------------
        "instagram_bio": (
            user_ig.get("bio")
            or user_ig.get("biography")
            or ""
        )[:500],

        "instagram_niche": (
            instagram_analysis.get("detected_niche")
            or user_ig.get("detected_niche")
        ),

        "instagram_categories": (
            discovery_features.get("instagram_categories")
            or instagram_analysis.get("content_categories")
            or []
        )[:10],

        "instagram_topics": (
            discovery_features.get("instagram_topics")
            or instagram_analysis.get("topics")
            or []
        )[:20],

        "instagram_posting_frequency": (
            discovery_features.get("instagram_posting_frequency")
        ),

        # --------------------------------------------------
        # LinkedIn Intelligence
        # --------------------------------------------------
        "linkedin_topics": (
            discovery_features.get("linkedin_topics")
            or []
        )[:20],

        "linkedin_categories": (
            discovery_features.get("linkedin_categories")
            or []
        )[:15],

        "linkedin_company_size": (
            discovery_features.get("company_size")
        ),

        "linkedin_is_hiring": (
            discovery_features.get("is_hiring")
        ),

        "linkedin_job_titles": (
            discovery_features.get("job_titles")
            or []
        )[:20],

        "linkedin_skills": (
            discovery_features.get("skills")
            or []
        )[:30],

        # --------------------------------------------------
        # Company Description
        # --------------------------------------------------
        "summary": (
            company_profile.get("summary")
            or company.get("description")
            or company.get("profile")
            or ""
        )[:1500],
    }


def _is_blocked_name(name: str) -> bool:
    from service.Competitor.competitor_name_filters import is_blocked_competitor_name

    return is_blocked_competitor_name(name)


def normalize_proposed_competitors(
    raw_competitors: list[dict[str, Any]],
    *,
    exclude_names: set[str],
    exclude_instagram: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_ig: set[str] = set()

    for item in raw_competitors:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if len(name) < 2:
            continue
        name_key = name.lower()
        if name_key in exclude_names or name_key in seen_names:
            continue

        ig = _normalize_instagram(item.get("instagram_username") or item.get("instagram"))
        if ig and (ig in exclude_instagram or ig in seen_ig):
            ig = None

        linkedin = _normalize_linkedin(item.get("linkedin_url") or item.get("linkedin"))
        website = (item.get("website") or "").strip() or None
        if website and not website.startswith("http"):
            website = f"https://{website}"

        candidate = {
            "name": name,
            "website": website,
            "linkedin_url": linkedin,
            "socials": {"instagram": ig, "linkedin": linkedin},
        }
        if is_junk_competitor(candidate):
            continue

        socials = filter_competitor_socials(
            {
                "instagram": ig,
                "linkedin": linkedin,
            }
        )
        if not any([ig, linkedin, website]):
            continue

        confidence = float(item.get("confidence") or 0.75)
        confidence = max(0.0, min(confidence, 1.0))

        payload = {
            "name": name,
            "username": ig,
            "website": website,
            "description": item.get("why_competitor") or item.get("description") or "",
            "socials": socials,
            "linkedin_url": linkedin,
            "instagram_username": ig,
            "why_competitor": item.get("why_competitor"),
            "region_fit": item.get("region_fit"),
            "services_overlap": _as_list(item.get("services_overlap"))[:8],
            "match_score": confidence,
            "confidence": confidence,
            "region_match": True,
            "niche_match": True,
            "authenticity": "openai_proposal",
            "source": "openai_competitor_proposal",
            "discovery_source": "openai_competitor_proposal",
        }
        results.append(payload)
        seen_names.add(name_key)
        if ig:
            seen_ig.add(ig)
        if len(results) >= limit:
            break

    return results