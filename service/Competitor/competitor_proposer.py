"""OpenAI-based authentic competitor proposal after user DNA is known."""

from __future__ import annotations

import logging
import re
from typing import Any

from config.credential_config import config
from prompts.competitor_proposal import SYSTEM_PROMPT
from service.Competitor.openai_client import chat_completion_json, resolve_openai_model
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
) -> dict[str, Any]:
    dna = company_analysis.get("company_dna") or {}
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
        "instagram_username": company.get("instagram_username") or user_ig.get("username"),
        "linkedin_url": company.get("linkedin_url"),
        "services": services[:20],
        "flagship_services": _as_list(company.get("flagship_services"))[:10],
        "technologies": technologies[:20],
        "keywords": keywords[:25],
        "target_audience": _as_list(dna.get("target_audience") or company_profile.get("target_audience"))[:15],
        "positioning": dna.get("positioning") or company_profile.get("positioning"),
        "value_proposition": dna.get("value_proposition") or company_profile.get("value_proposition"),
        "summary": (company_profile.get("summary") or company.get("description") or company.get("profile") or "")[:1200],
        "instagram_bio": (user_ig.get("bio") or user_ig.get("biography") or "")[:500],
        "instagram_niche": user_ig.get("detected_niche"),
        "linkedin_positioning": (user_li.get("b2b_positioning") or user_li.get("thought_leadership") or {})
        if isinstance(user_li, dict)
        else {},
        "linkedin_sample_topics": [
            (post.get("text") or "")[:160]
            for post in (user_li.get("sample_posts") or user_li.get("posts") or [])[:5]
            if isinstance(post, dict)
        ],
    }


def _is_blocked_name(name: str) -> bool:
    lowered = (name or "").lower()
    blocked = (
        "top ai",
        "top artificial",
        "best ai",
        "best artificial",
        "companies in",
        "dominating",
        "revealed",
        "list of",
        "ranking",
        "peoplepakistan",
    )
    return any(token in lowered for token in blocked)


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
        if len(name) < 2 or _is_blocked_name(name):
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


class CompetitorProposerService:
    async def propose(
        self,
        *,
        company: dict[str, Any],
        company_profile: dict[str, Any],
        company_analysis: dict[str, Any],
        region: str,
        limit: int = MIN_COMPETITORS,
        hints: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not (config.OPENAI_API_KEY or "").strip():
            raise ValueError("OPENAI_API_KEY is not configured")

        target = max(int(limit or MIN_COMPETITORS), MIN_COMPETITORS)
        dna = _build_user_dna_blob(
            company=company,
            company_profile=company_profile,
            company_analysis=company_analysis,
        )
        own_name = (dna.get("name") or "").strip().lower()
        own_ig = (dna.get("instagram_username") or "").strip().lstrip("@").lower()

        user_prompt = f"""
Region focus: {region}
Requested authentic competitors: {target} (return at least {target})

User company DNA (from profile + Instagram + LinkedIn analysis):
{dna}

Optional known competitor hints (validate; discard if not real peers):
{hints or []}

Propose {target}+ real competitors that sell overlapping services to similar buyers in/around {region}.
"""
        data = await chat_completion_json(
            model=resolve_openai_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            timeout=120,
        )
        raw = data.get("competitors") or []
        if not isinstance(raw, list):
            raw = []

        competitors = normalize_proposed_competitors(
            raw,
            exclude_names={own_name} if own_name else set(),
            exclude_instagram={own_ig} if own_ig else set(),
            limit=max(target + 5, target),
        )
        meta = {
            "matching_mode": "openai_proposal",
            "discovery_source": "openai_competitor_proposal",
            "competitor_target": target,
            "openai_returned": len(raw),
            "openai_accepted": len(competitors),
            "reasoning": data.get("reasoning"),
        }
        logger.info(
            "OpenAI proposed %s competitors (accepted %s) for region=%s",
            len(raw),
            len(competitors),
            region,
        )
        return competitors[:target], meta
