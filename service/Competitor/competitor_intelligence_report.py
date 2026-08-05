from __future__ import annotations
from collections import Counter
from typing import Any

from models.company import CompanyProfile
from service.Competitor.competitor_ranker import CompetitorRanker
from service.Competitor.signal_extractor import (
    build_extended_linkedin_profile,
    collect_text_blobs,
    extract_business_signals,
    extract_content_signals,
    extract_industries_targeted,
    extract_review_presence,
    extract_technologies_mentioned,
)

SIMILARITY_KEYS = (
    "services",
    "technology",
    "target_audience",
    "industry",
    "pricing",
    "location",
    "marketing",
    "content",
    "overall",
)

BUSINESS_SIGNAL_KEYS = (
    "hiring",
    "funding",
    "acquisition",
    "expansion",
    "awards",
    "events",
    "partnerships",
    "press_releases",
    "speaking_events",
    "podcasts",
)

REVIEW_PLATFORMS = ("clutch", "g2", "trustpilot", "google_reviews")


def _user_entity(
    company: CompanyProfile,
    *,
    company_analysis: dict[str, Any] | None,
    company_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    analysis = company_analysis or {}
    user_li = analysis.get("user_linkedin") or {}
    user_ig = analysis.get("user_instagram") or {}
    profile = company_profile or {}

    return {
        "name": company.name,
        "website": company.website or profile.get("website"),
        "industry": company.industry,
        "services": company.services,
        "technologies": company.technologies,
        "target_audience": company.target_audience,
        "country": company.country,
        "city": company.city,
        "region": company.region,
        "pricing_model": company.pricing_model,
        "bio": user_ig.get("bio") or profile.get("description"),
        "tagline": profile.get("value_proposition") or company.positioning,
        "website_intelligence": profile,
        "linkedin_analysis": user_li.get("linkedin_analysis") or analysis.get("linkedin_analysis"),
        "linkedin_posts": user_li.get("linkedin_posts") or analysis.get("linkedin_posts") or [],
        "instagram_posts": user_ig.get("posts") or analysis.get("instagram_posts") or [],
        "instagram_analysis": user_ig.get("instagram") or analysis.get("instagram"),
        "user_linkedin": user_li,
        "employees": user_li.get("employees") or [],
        "job_openings": user_li.get("job_openings") or [],
        "company_size": user_li.get("company_size"),
        "followers": user_li.get("followers"),
        "specialties": company.services,
        "headquarters": company.city or company.country,
    }


def _normalize_similarity(score: dict[str, Any]) -> dict[str, float]:
    return {
        "services": float(score.get("products") or score.get("services") or 0),
        "technology": float(score.get("technology") or 0),
        "target_audience": float(score.get("audience") or 0),
        "industry": float(score.get("industry") or 0),
        "pricing": float(score.get("pricing") or 0),
        "location": float(score.get("geography") or 0),
        "marketing": float(score.get("positioning") or score.get("social_strategy") or 0),
        "content": float(score.get("content_strategy") or 0),
        "overall": float(score.get("overall") or 0),
    }


def _content_similarity(user: dict[str, Any], competitor: dict[str, Any]) -> float:
    user_themes = set()
    comp_themes = set()
    user_ig = user.get("instagram_analysis") or {}
    comp_ig = competitor.get("instagram_analysis") or {}
    for theme in user_ig.get("content_themes") or []:
        if isinstance(theme, dict):
            user_themes.add(str(theme.get("theme") or "").lower())
        else:
            user_themes.add(str(theme).lower())
    for theme in comp_ig.get("content_themes") or []:
        if isinstance(theme, dict):
            comp_themes.add(str(theme.get("theme") or "").lower())
        else:
            comp_themes.add(str(theme).lower())
    user_li = user.get("linkedin_analysis") or {}
    comp_li = competitor.get("linkedin_analysis") or {}
    for theme in user_li.get("content_themes") or []:
        user_themes.add(str(theme).lower())
    for theme in comp_li.get("content_themes") or []:
        comp_themes.add(str(theme).lower())
    user_themes.discard("")
    comp_themes.discard("")
    if not user_themes or not comp_themes:
        return 0.0
    overlap = user_themes & comp_themes
    return round(min(len(overlap) / max(len(user_themes), 1), 1.0), 3)


def _marketing_similarity(user: dict[str, Any], competitor: dict[str, Any]) -> float:
    user_text = collect_text_blobs(user).lower()
    comp_text = collect_text_blobs(competitor).lower()
    marketing_terms = (
        "digital marketing",
        "content marketing",
        "seo",
        "social media",
        "brand",
        "campaign",
        "lead generation",
        "b2b",
        "thought leadership",
    )
    user_hits = sum(1 for term in marketing_terms if term in user_text)
    comp_hits = sum(1 for term in marketing_terms if term in comp_text)
    if user_hits == 0 and comp_hits == 0:
        return 0.0
    shared = sum(1 for term in marketing_terms if term in user_text and term in comp_text)
    return round(shared / max(user_hits, comp_hits, 1), 3)


def _pricing_similarity(company: CompanyProfile, competitor: dict[str, Any]) -> float:
    user_model = (company.pricing_model or "").lower()
    comp_text = collect_text_blobs(competitor).lower()
    pricing_terms = (
        "subscription",
        "monthly",
        "annual",
        "enterprise",
        "freemium",
        "pay as you go",
        "fixed price",
        "hourly",
        "project-based",
        "custom quote",
    )
    if user_model:
        return 0.7 if user_model in comp_text else 0.3
    user_hits = {t for t in pricing_terms if t in (company.description or "").lower()}
    comp_hits = {t for t in pricing_terms if t in comp_text}
    if not user_hits and not comp_hits:
        return 0.0
    if not user_hits or not comp_hits:
        return 0.2
    return round(len(user_hits & comp_hits) / max(len(user_hits | comp_hits), 1), 3)


def _competitor_gaps(
    user: dict[str, Any],
    competitors: list[dict[str, Any]],
    *,
    gap_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    user_services = {s.lower() for s in (user.get("services") or []) if s}
    user_tech = {t.lower() for t in (user.get("technologies") or []) if t}
    user_text = collect_text_blobs(user).lower()
    user_signals = set(extract_business_signals(user_text)["active_signals"])
    user_content = set(extract_content_signals(user_text)["active_content_types"])
    user_industries = set(extract_industries_targeted(user_text))
    user_reviews = set(extract_review_presence(user_text)["present_on"])

    comp_services: Counter[str] = Counter()
    comp_tech: Counter[str] = Counter()
    comp_signals: Counter[str] = Counter()
    comp_content: Counter[str] = Counter()
    comp_industries: Counter[str] = Counter()
    comp_reviews: Counter[str] = Counter()

    for comp in competitors:
        for svc in comp.get("website_services") or []:
            comp_services[str(svc).lower()] += 1
        intel = comp.get("website_intelligence") or {}
        for svc in intel.get("services") or []:
            comp_services[str(svc).lower()] += 1
        for tech in intel.get("technologies") or []:
            comp_tech[str(tech).lower()] += 1
        text = collect_text_blobs(comp)
        for sig in extract_business_signals(text)["active_signals"]:
            comp_signals[sig] += 1
        for ctype in extract_content_signals(text)["active_content_types"]:
            comp_content[ctype] += 1
        for ind in extract_industries_targeted(text):
            comp_industries[ind] += 1
        links = [comp.get("website") or "", comp.get("linkedin_url") or ""]
        for platform in extract_review_presence(text, links=links)["present_on"]:
            comp_reviews[platform] += 1

    threshold = max(1, len(competitors) // 3)

    def _gap_items(counter: Counter[str], user_set: set[str], limit: int = 12) -> list[dict[str, Any]]:
        items = []
        for key, count in counter.most_common(limit + len(user_set)):
            if key in user_set:
                continue
            if count >= threshold:
                items.append({"item": key, "competitor_count": count})
            if len(items) >= limit:
                break
        return items

    service_gaps = _gap_items(comp_services, user_services)
    tech_gaps = _gap_items(comp_tech, user_tech, limit=10)
    signal_gaps = [
        {"signal": sig, "competitor_count": count}
        for sig, count in comp_signals.most_common()
        if sig not in user_signals and count >= threshold
    ]
    content_gaps = [
        {"content_type": ctype, "competitor_count": count}
        for ctype, count in comp_content.most_common()
        if ctype not in user_content and count >= threshold
    ]
    industry_gaps = [
        {"industry": ind, "competitor_count": count}
        for ind, count in comp_industries.most_common()
        if ind not in user_industries and count >= threshold
    ]
    review_gaps = [
        {"platform": platform, "competitor_count": count}
        for platform, count in comp_reviews.most_common()
        if platform not in user_reviews
    ]

    merged_service_gaps = list(
        dict.fromkeys(
            [g["item"] for g in service_gaps]
            + (gap_analysis.get("service_gaps") or [])
        )
    )[:12]

    return {
        "services": merged_service_gaps,
        "technologies": [g["item"] for g in tech_gaps],
        "business_signals": signal_gaps,
        "content_types": content_gaps,
        "industries_targeted": industry_gaps,
        "review_platforms": review_gaps,
        "summary": (
            f"Competitors do {len(merged_service_gaps)} services, "
            f"{len(tech_gaps)} technologies, and "
            f"{len(signal_gaps)} business activities you don't emphasize."
        ),
    }


def _aggregate_business_signals(
    user: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    user_text = collect_text_blobs(user)
    user_flags = extract_business_signals(user_text)["signals"]

    competitor_matrix: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()

    for comp in competitors:
        text = collect_text_blobs(comp)
        signals = extract_business_signals(text)
        flags = signals["signals"]
        for key in BUSINESS_SIGNAL_KEYS:
            if flags.get(key):
                totals[key] += 1
        competitor_matrix.append(
            {
                "name": comp.get("name"),
                "signals": flags,
                "active_signals": signals["active_signals"],
            }
        )

    user_active = [k for k, v in user_flags.items() if v]
    competitor_only = [
        {
            "signal": key,
            "competitor_count": totals[key],
            "user_has": user_flags.get(key, False),
        }
        for key in BUSINESS_SIGNAL_KEYS
        if totals[key] > 0
    ]

    return {
        "user": {"signals": user_flags, "active_signals": user_active},
        "competitors": competitor_matrix,
        "market_prevalence": [
            {"signal": key, "competitor_count": totals[key]}
            for key in BUSINESS_SIGNAL_KEYS
            if totals[key] > 0
        ],
        "competitor_only_signals": [
            item for item in competitor_only if not item["user_has"]
        ],
    }


def _review_intelligence(
    user: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    user_text = collect_text_blobs(user)
    user_reviews = extract_review_presence(user_text, links=[user.get("website") or ""])

    competitor_reviews: list[dict[str, Any]] = []
    platform_counts: Counter[str] = Counter()

    for comp in competitors:
        text = collect_text_blobs(comp)
        links = [comp.get("website") or "", comp.get("linkedin_url") or ""]
        presence = extract_review_presence(text, links=links)
        for platform in presence["present_on"]:
            platform_counts[platform] += 1
        competitor_reviews.append(
            {
                "name": comp.get("name"),
                "platforms": presence["platforms"],
                "present_on": presence["present_on"],
            }
        )

    user_present = set(user_reviews["present_on"])
    gaps = [
        {"platform": platform, "competitor_count": platform_counts[platform]}
        for platform in REVIEW_PLATFORMS
        if platform in platform_counts and platform not in user_present
    ]

    return {
        "user": user_reviews,
        "competitors": competitor_reviews,
        "market_presence": [
            {"platform": platform, "competitor_count": count}
            for platform, count in platform_counts.most_common()
        ],
        "gaps": gaps,
    }


def build_competitor_intelligence_report(
    *,
    company: CompanyProfile,
    competitors: list[dict[str, Any]],
    company_analysis: dict[str, Any] | None = None,
    company_profile: dict[str, Any] | None = None,
    gap_analysis: dict[str, Any] | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Full user-vs-competitor report with similarity, gaps, signals, reviews, LinkedIn."""
    user = _user_entity(company, company_analysis=company_analysis, company_profile=company_profile)
    ranker = CompetitorRanker()

    similarity_comparisons: list[dict[str, Any]] = []
    for comp in competitors:
        base_score = ranker.score_candidate(company, comp, region=region)
        normalized = _normalize_similarity(base_score)
        normalized["content"] = max(
            normalized["content"],
            _content_similarity(user, comp),
        )
        normalized["marketing"] = max(
            normalized["marketing"],
            _marketing_similarity(user, comp),
        )
        normalized["pricing"] = max(
            normalized["pricing"],
            _pricing_similarity(company, comp),
        )
        normalized["services"] = max(
            normalized["services"],
            float(base_score.get("products") or 0),
        )
        normalized["overall"] = round(
            normalized["services"] * 0.18
            + normalized["technology"] * 0.12
            + normalized["target_audience"] * 0.10
            + normalized["industry"] * 0.12
            + normalized["pricing"] * 0.08
            + normalized["location"] * 0.12
            + normalized["marketing"] * 0.10
            + normalized["content"] * 0.18,
            3,
        )
        similarity_comparisons.append(
            {
                "name": comp.get("name"),
                "username": comp.get("username"),
                "website": comp.get("website"),
                "similarity": normalized,
            }
        )

    similarity_comparisons.sort(
        key=lambda item: float(item["similarity"]["overall"]),
        reverse=True,
    )

    user_linkedin = build_extended_linkedin_profile(user, is_user=True)
    competitor_linkedin = [
        {
            "name": comp.get("name"),
            "linkedin_url": comp.get("linkedin_url"),
            **build_extended_linkedin_profile(comp),
        }
        for comp in competitors
    ]

    gaps = _competitor_gaps(user, competitors, gap_analysis=gap_analysis)
    business_signals = _aggregate_business_signals(user, competitors)
    review_intelligence = _review_intelligence(user, competitors)

    avg_similarity = {
        key: round(
            sum(item["similarity"][key] for item in similarity_comparisons)
            / max(len(similarity_comparisons), 1),
            3,
        )
        for key in SIMILARITY_KEYS
    }

    return {
        "user_company": {
            "name": company.name,
            "website": company.website,
            "industry": company.industry,
            "services": company.services,
            "technologies": company.technologies,
            "target_audience": company.target_audience,
            "region": company.region or region,
        },
        "competitor_count": len(competitors),
        "similarity_vs_competitors": similarity_comparisons,
        "average_similarity": avg_similarity,
        "gaps": gaps,
        "business_signals": business_signals,
        "review_intelligence": review_intelligence,
        "linkedin_analysis": {
            "user": user_linkedin,
            "competitors": competitor_linkedin,
        },
        "summary": (
            f"Compared {company.name} against {len(competitors)} competitors. "
            f"Overall similarity avg: {avg_similarity['overall']:.0%}. "
            f"{gaps['summary']}"
        ),
    }
