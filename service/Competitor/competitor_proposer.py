"""OpenAI-based authentic competitor proposal after user DNA is known."""

from __future__ import annotations

import logging
import re
from typing import Any

from config.credential_config import config
from prompts.competitor_proposal import SYSTEM_PROMPT
from service.Competitor.openai_client import chat_completion_json, resolve_openai_model
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

        # --------------------------------------------------
        # Core Business DNA
        # --------------------------------------------------
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


class CompetitorProposerService:

    async def propose(
    self,
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any],
    company_signals: dict[str, Any] | None = None,
    discovery_features: dict[str, Any] | None = None,
    instagram_analysis: dict[str, Any] | None = None,
    linkedin_analysis: dict[str, Any] | None = None,
    website_intelligence: dict[str, Any] | None = None,
    region: str,
    limit: int = MIN_COMPETITORS,
    hints: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not (config.OPENAI_API_KEY or "").strip():
            raise ValueError("OPENAI_API_KEY is not configured")

        target = max(1, int(limit or MIN_COMPETITORS))
        dna = _build_user_dna_blob(
        company=company,
        company_profile=company_profile,
        company_analysis=company_analysis,
        company_signals=company_signals,
        discovery_features=discovery_features,
        instagram_analysis=instagram_analysis,
        linkedin_analysis=linkedin_analysis,
        website_intelligence=website_intelligence,
)
        own_name = (dna.get("name") or "").strip().lower()
        own_ig = (dna.get("instagram_username") or "").strip().lstrip("@").lower()
        services = dna.get("services") or []
        technologies = dna.get("technologies") or []
        keywords = dna.get("keywords") or []

        instagram_topics = dna.get("instagram_topics") or []
        linkedin_topics = dna.get("linkedin_topics") or []

        website_services = dna.get("website_services") or []
        target_audience = dna.get("target_audience") or []
        company_size = dna.get("linkedin_company_size")
        is_hiring = dna.get("linkedin_is_hiring")

        user_prompt = f"""
You are identifying REAL competitors for a company.Think carefully before selecting competitors.

Internally perform these steps:

STEP 1
Understand exactly what this company sells.

STEP 2
Identify its primary customer.

STEP 3
Identify secondary customer segments.

STEP 4
Determine the company's business model.

Examples:
• Software Company
• SaaS
• Marketing Agency
• AI Consultancy
• Cloud Consultancy
• Healthcare
• Fintech
• Real Estate
• E-commerce
• Manufacturing
• Recruitment

STEP 5
Determine company size.

Examples:
Startup
SME
Mid Market
Enterprise

STEP 6
Determine geographic market.

Examples:
Pakistan
Middle East
UAE
Saudi Arabia
Global

STEP 7
Determine service overlap.

Competitors should share at least
70% of services.

STEP 8
Determine customer overlap.

Competitors should target similar customers.

STEP 9
Determine positioning overlap.

Compare:

• pricing
• expertise
• technologies
• industry focus
• messaging
• specialization

STEP 10
Score every candidate.

Score based on

Service similarity 35%

Customer similarity 25%

Industry overlap 15%

Region overlap 10%

Technology overlap 10%

Social presence 5%

Only keep competitors with
Similarity Score >= 70.

If fewer than requested exist,
return only authentic competitors.
Never invent companies.
Never return companies that only have similar keywords.
Think carefully before producing the final JSON.

Only return companies that genuinely compete for the SAME customers.

STEP 11

Before selecting a competitor, verify that:

- The company currently exists.
- The company actively provides these services.
- The company operates in the specified region.
- The website clearly describes similar offerings.
- At least one public source confirms the company.

Reject companies if any of these checks fail.

----------------------------------------------------
COMPANY
----------------------------------------------------

Name:
{dna.get("name")}

Region:
{region}

Business Summary:
{dna.get("summary")}

Positioning:
{dna.get("positioning")}

Value Proposition:
{dna.get("value_proposition")}

----------------------------------------------------
SERVICES
----------------------------------------------------

Primary Services

{services}

Website Services

{website_services}

----------------------------------------------------
TECHNOLOGY
----------------------------------------------------

Technologies

{technologies}

----------------------------------------------------
TARGET AUDIENCE
----------------------------------------------------

{target_audience}

----------------------------------------------------
CONTENT STRATEGY
----------------------------------------------------

Instagram Topics

{instagram_topics}

LinkedIn Topics

{linkedin_topics}

Keywords

{keywords}

----------------------------------------------------
SOCIAL SIGNALS
----------------------------------------------------

Instagram Username

{dna.get("instagram_username")}

LinkedIn Company Size

{company_size}

Currently Hiring

{is_hiring}

----------------------------------------------------
RULES
----------------------------------------------------

Return ONLY companies that satisfy ALL conditions:

1.Offer very similar services.
2.Target the same customer type.
3.Operate in the same region.
4.Similar company size.
5.Compete for the same projects.
6.Not marketplaces.
7.Not agencies unless this company is an agency.
8.Not software vendors unless this company sells software.
9.Not partners.
10.Not technology providers.
11.Not clients.
12.Not investors.
13.Not media companies.
14.Must have an active business website.
15.Must have either Instagram OR LinkedIn.
16.Must currently be operating.
17.Avoid multinational giants if the user company is SME.
18.Prefer companies with similar employee count.
19.Prefer companies with similar service portfolio.
20.Return the BEST {limit} competitors.
----------------------------------------------------
FOR EACH COMPETITOR RETURN
Company Name
Website
Why they compete
Similarity Score (0-100)
Services
Country
City
Instagram Username
LinkedIn URL
Confidence (0-1)
----------------------------------------------------
Return ONLY JSON.

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
