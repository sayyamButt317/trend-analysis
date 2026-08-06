from __future__ import annotations
from collections import Counter
from typing import Any

from models.company import CompanyProfile
from service.Competitor.competitor_ranker import CompetitorRanker, _region_terms, _text_hits
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

UI_SIMILARITY_KEYS = (
    "overall",
    "services",
    "technology",
    "marketing",
    "content",
    "location",
)


def similarity_to_percentages(similarity: dict[str, Any]) -> dict[str, int]:
    """Map 0-1 similarity scores to 0-100 percentages for the overview table."""
    return {
        "overall": round(float(similarity.get("overall") or 0) * 100),
        "services": round(float(similarity.get("services") or 0) * 100),
        "tech": round(float(similarity.get("technology") or similarity.get("tech") or 0) * 100),
        "marketing": round(float(similarity.get("marketing") or 0) * 100),
        "content": round(float(similarity.get("content") or 0) * 100),
        "location": round(float(similarity.get("location") or 0) * 100),
    }


def _competitor_lookup_key(item: dict[str, Any]) -> str:
    username = (item.get("username") or "").strip().lstrip("@").lower()
    if username:
        return f"u:{username}"
    name = (item.get("name") or "").strip().lower()
    if name:
        return f"n:{name}"
    website = (item.get("website") or "").strip().lower()
    if website:
        return f"w:{website}"
    return ""


def _term_list_overlap(a: list[str], b: list[str]) -> float:
    set_a = {str(item).lower().strip() for item in a if item and str(item).strip()}
    set_b = {str(item).lower().strip() for item in b if item and str(item).strip()}
    if not set_a or not set_b:
        return 0.0
    direct = len(set_a & set_b) / max(len(set_a), 1)
    partial_hits = 0
    for left in set_a:
        for right in set_b:
            if left in right or right in left:
                partial_hits += 1
                break
    partial = partial_hits / max(len(set_a), 1)
    return round(min(max(direct, partial * 0.75), 1.0), 3)


def _service_terms(entity: dict[str, Any], company: CompanyProfile | None = None) -> list[str]:
    terms: list[str] = []
    if company:
        terms.extend(company.services or [])
        terms.extend(company.products or [])
    terms.extend(entity.get("services") or [])
    terms.extend(entity.get("website_services") or [])
    terms.extend(entity.get("specialties") or [])
    intel = entity.get("website_intelligence") or {}
    terms.extend(intel.get("services") or [])
    li = entity.get("linkedin_analysis") or {}
    terms.extend(str(item) for item in (li.get("specialties") or []))
    ig = entity.get("instagram_analysis") or {}
    if ig.get("content_focus"):
        terms.append(str(ig["content_focus"]))
    for category in ig.get("content_categories") or []:
        if isinstance(category, dict):
            terms.append(str(category.get("category") or ""))
        else:
            terms.append(str(category))
    return [term for term in terms if term and str(term).strip()]


def _technology_terms(entity: dict[str, Any], company: CompanyProfile | None = None) -> list[str]:
    terms: list[str] = []
    if company:
        terms.extend(company.technologies or [])
    terms.extend(entity.get("technologies") or [])
    intel = entity.get("website_intelligence") or {}
    terms.extend(intel.get("technologies") or [])
    li = entity.get("linkedin_analysis") or {}
    terms.extend(str(item) for item in (li.get("technologies_mentioned") or []))
    terms.extend(extract_technologies_mentioned(collect_text_blobs(entity)))
    return [term for term in terms if term and str(term).strip()]


def _services_similarity(
    user: dict[str, Any],
    competitor: dict[str, Any],
    company: CompanyProfile,
) -> float:
    user_terms = _service_terms(user, company)
    comp_terms = _service_terms(competitor)
    list_score = _term_list_overlap(user_terms, comp_terms)
    user_text = collect_text_blobs(user).lower()
    comp_text = collect_text_blobs(competitor).lower()
    text_score = 0.0
    for term in {str(item).lower().strip() for item in user_terms if item}:
        if term in comp_text or any(term in other or other in term for other in comp_terms):
            text_score += 1
    text_score = text_score / max(len({str(item).lower().strip() for item in user_terms if item}), 1)
    return round(min(max(list_score, text_score * 0.85), 1.0), 3)


def _technology_similarity(
    user: dict[str, Any],
    competitor: dict[str, Any],
    company: CompanyProfile,
) -> float:
    user_terms = _technology_terms(user, company)
    comp_terms = _technology_terms(competitor)
    return max(
        _term_list_overlap(user_terms, comp_terms),
        _term_list_overlap(
            extract_technologies_mentioned(collect_text_blobs(user)),
            extract_technologies_mentioned(collect_text_blobs(competitor)),
        ),
    )


def _location_similarity(
    user: dict[str, Any],
    competitor: dict[str, Any],
    company: CompanyProfile,
    region: str | None,
) -> float:
    user_locations = {
        str(value).lower().strip()
        for value in (
            company.city,
            company.country,
            company.region,
            region,
            user.get("city"),
            user.get("country"),
            user.get("region"),
            user.get("headquarters"),
        )
        if value
    }
    comp_locations: set[str] = set()
    for value in (
        competitor.get("city"),
        competitor.get("country"),
        competitor.get("headquarters"),
        (competitor.get("linkedin_analysis") or {}).get("headquarters"),
        (competitor.get("linkedin_analysis") or {}).get("location"),
    ):
        if value:
            comp_locations.add(str(value).lower().strip())

    comp_text = collect_text_blobs(competitor).lower()
    score = 0.0
    for user_loc in user_locations:
        for comp_loc in comp_locations:
            if user_loc in comp_loc or comp_loc in user_loc:
                score = max(score, 0.95)
        if user_loc in comp_text:
            score = max(score, 0.75)

    region_terms = _region_terms(region, company)
    if region_terms and _text_hits(comp_text, region_terms):
        score = max(score, 0.65)
    if company.country and company.country.lower() in comp_text:
        score = max(score, 0.7)
    if company.city and company.city.lower() in comp_text:
        score = max(score, 0.85)
    if competitor.get("region_match") is True:
        score = max(score, 0.8)
    return round(min(score, 1.0), 3) if score else 0.15


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


def compute_competitor_similarity(
    *,
    user: dict[str, Any],
    competitor: dict[str, Any],
    company: CompanyProfile,
    region: str | None = None,
) -> dict[str, float]:
    """Compute per-competitor similarity across the six overview dimensions."""
    ranker = CompetitorRanker()
    base_score = ranker.score_candidate(company, competitor, region=region)

    services = max(
        float(base_score.get("services") or 0),
        _services_similarity(user, competitor, company),
    )
    technology = max(
        float(base_score.get("technology") or 0),
        _technology_similarity(user, competitor, company),
    )
    marketing = max(
        float(base_score.get("marketing") or 0),
        _marketing_similarity(user, competitor, company=company),
    )
    content = max(
        float(base_score.get("content") or base_score.get("content_strategy") or 0),
        _content_similarity(user, competitor),
    )
    location = max(
        float(base_score.get("location") or base_score.get("geography") or 0),
        _location_similarity(user, competitor, company, region),
    )
    overall = round(
        services * 0.25
        + technology * 0.15
        + marketing * 0.20
        + content * 0.25
        + location * 0.15,
        3,
    )
    return {
        "services": round(services, 3),
        "technology": round(technology, 3),
        "marketing": round(marketing, 3),
        "content": round(content, 3),
        "location": round(location, 3),
        "overall": overall,
        "target_audience": float(base_score.get("target_audience") or base_score.get("audience") or 0),
        "industry": float(base_score.get("industry") or 0),
        "pricing": max(
            float(base_score.get("pricing") or 0),
            _pricing_similarity(company, competitor),
        ),
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
    theme_score = 0.0
    if user_themes and comp_themes:
        overlap = user_themes & comp_themes
        theme_score = min(len(overlap) / max(len(user_themes), 1), 1.0)

    user_hashtags = {
        str(tag).lower().lstrip("#")
        for tag in (user_ig.get("top_hashtags") or [])
        if tag
    }
    comp_hashtags = {
        str(tag).lower().lstrip("#")
        for tag in (comp_ig.get("top_hashtags") or [])
        if tag
    }
    hashtag_score = 0.0
    if user_hashtags and comp_hashtags:
        hashtag_score = len(user_hashtags & comp_hashtags) / max(len(user_hashtags), 1)

    format_score = 0.0
    user_format = user_ig.get("primary_format")
    comp_format = comp_ig.get("primary_format")
    if user_format and comp_format and str(user_format).lower() == str(comp_format).lower():
        format_score = 0.45

    category_score = 0.0
    user_category = user_ig.get("primary_content_category")
    comp_category = comp_ig.get("primary_content_category")
    if user_category and comp_category and str(user_category).lower() == str(comp_category).lower():
        category_score = 0.35

    combined = max(
        theme_score,
        min(hashtag_score * 0.85 + format_score * 0.35 + category_score * 0.25, 1.0),
    )
    if combined == 0.0 and user_ig and comp_ig:
        combined = 0.2
    return round(min(combined, 1.0), 3)


def _marketing_similarity(
    user: dict[str, Any],
    competitor: dict[str, Any],
    *,
    company: CompanyProfile | None = None,
) -> float:
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
        "software development",
        "consulting",
        "technology services",
    )
    user_hits = sum(1 for term in marketing_terms if term in user_text)
    comp_hits = sum(1 for term in marketing_terms if term in comp_text)
    shared = sum(1 for term in marketing_terms if term in user_text and term in comp_text)
    term_score = shared / max(user_hits, comp_hits, 1) if (user_hits or comp_hits) else 0.0

    keyword_score = 0.0
    if company:
        keywords = [str(keyword).lower() for keyword in (company.keywords or [])[:12] if keyword]
        if keywords:
            keyword_hits = sum(1 for keyword in keywords if keyword in user_text and keyword in comp_text)
            keyword_score = keyword_hits / max(len(keywords), 1)

    user_channels = set()
    comp_channels = set()
    if user.get("instagram_analysis"):
        user_channels.add("instagram")
    if user.get("linkedin_analysis") or user.get("user_linkedin"):
        user_channels.add("linkedin")
    if competitor.get("instagram_analysis"):
        comp_channels.add("instagram")
    if competitor.get("linkedin_analysis"):
        comp_channels.add("linkedin")
    channel_score = 0.0
    if user_channels and comp_channels:
        channel_score = len(user_channels & comp_channels) / max(len(user_channels | comp_channels), 1)

    user_li = user.get("linkedin_analysis") or {}
    comp_li = competitor.get("linkedin_analysis") or {}
    thought_score = 0.0
    user_tl = float(user_li.get("thought_leadership_score") or 0)
    comp_tl = float(comp_li.get("thought_leadership_score") or 0)
    if user_tl and comp_tl:
        thought_score = 1.0 - min(abs(user_tl - comp_tl), 1.0)

    return round(min(max(term_score, keyword_score, channel_score * 0.65, thought_score * 0.5), 1.0), 3)


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
        for svc in _service_terms(comp):
            comp_services[str(svc).lower()] += 1
        for tech in intel.get("technologies") or []:
            comp_tech[str(tech).lower()] += 1
        for tech in _technology_terms(comp):
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
            + ((gap_analysis or {}).get("service_gaps") or [])
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

    similarity_comparisons: list[dict[str, Any]] = []
    for comp in competitors:
        normalized = compute_competitor_similarity(
            user=user,
            competitor=comp,
            company=company,
            region=region,
        )
        similarity_comparisons.append(
            {
                "name": comp.get("name"),
                "username": comp.get("username"),
                "website": comp.get("website"),
                "similarity": normalized,
                "similarity_percentages": similarity_to_percentages(normalized),
                "match_score": normalized["overall"],
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
        for key in (*UI_SIMILARITY_KEYS, "target_audience", "industry", "pricing")
        if any(key in item["similarity"] for item in similarity_comparisons)
    }
    avg_similarity["similarity_percentages"] = similarity_to_percentages(avg_similarity)

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
