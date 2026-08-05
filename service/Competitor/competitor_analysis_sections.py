from __future__ import annotations
from collections import Counter
from typing import Any


def _swot_analysis(
    *,
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    intel_report: dict[str, Any],
    gap_analysis: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    gaps = intel_report.get("gaps") or {}
    business = intel_report.get("business_signals") or {}
    user_signals = list((business.get("user") or {}).get("active_signals") or [])
    competitor_only = [
        item.get("signal")
        for item in (business.get("competitor_only_signals") or [])
        if item.get("signal")
    ]

    strengths: list[str] = []
    for svc in (company_profile.get("services") or [])[:5]:
        strengths.append(f"Offers {svc}")
    for tech in (company_profile.get("technologies") or [])[:4]:
        strengths.append(f"Uses {tech}")
    if user_signals:
        strengths.append(f"Active business signals: {', '.join(user_signals[:4])}")

    user_ig = ((company_analysis or {}).get("user_instagram") or {}).get("instagram") or {}
    if user_ig.get("avg_engagement_rate"):
        strengths.append(f"Instagram engagement rate: {user_ig['avg_engagement_rate']}%")

    weaknesses: list[str] = []
    for svc in (gaps.get("services") or [])[:4]:
        weaknesses.append(f"Missing service/theme: {svc}")
    for tech in (gaps.get("technologies") or gap_analysis.get("technology_gaps") or [])[:4]:
        weaknesses.append(f"Missing technology focus: {tech}")
    for sig in competitor_only[:4]:
        weaknesses.append(f"Competitors promote {sig.replace('_', ' ')} — you don't")

    opportunities: list[str] = []
    for gap in (intel_report.get("review_intelligence") or {}).get("gaps") or []:
        platform = gap.get("platform", "").replace("_", " ")
        opportunities.append(f"Build presence on {platform}")
    for ctype in gaps.get("content_types") or []:
        label = (ctype.get("content_type") or "").replace("_", " ")
        opportunities.append(f"Publish more {label} content")
    for ind in gaps.get("industries_targeted") or []:
        opportunities.append(f"Target {ind.get('industry')} segment")

    threats: list[str] = []
    hiring_count = sum(
        1 for c in competitors if (c.get("linkedin_analysis") or {}).get("is_hiring")
    )
    if hiring_count >= 2:
        threats.append(f"{hiring_count} competitors are actively hiring")
    for comp in (intel_report.get("similarity_vs_competitors") or [])[:3]:
        score = (comp.get("similarity") or {}).get("overall", 0)
        if score >= 0.6:
            threats.append(f"High overlap with {comp.get('name')} (similarity {score:.0%})")
    for sig in ("funding", "expansion", "acquisition"):
        count = sum(
            1
            for row in (business.get("competitors") or [])
            if sig in (row.get("active_signals") or [])
        )
        if count >= 2:
            threats.append(f"{count} competitors show {sig.replace('_', ' ')} signals")

    return {
        "strengths": strengths[:8],
        "weaknesses": weaknesses[:8],
        "opportunities": opportunities[:8],
        "threats": threats[:8],
    }


def _seo_section(
    *,
    company_profile: dict[str, Any],
    search_intelligence: dict[str, Any] | None,
    web_crawl: dict[str, Any] | None,
    gap_analysis: dict[str, Any],
    intel_report: dict[str, Any],
) -> dict[str, Any]:
    profile = company_profile or {}
    search = search_intelligence or {}
    crawl = web_crawl or {}

    keywords = list(
        dict.fromkeys(
            (profile.get("keywords") or [])
            + (search.get("search_keywords") or [])
            + (crawl.get("keywords") or [])
            + (search.get("industry_terms") or [])
            + (search.get("product_terms") or [])
        )
    )[:20]

    queries = (search.get("search_queries") or [])[:10]
    keyword_gaps = gap_analysis.get("keyword_gaps") or []
    competitor_keywords: Counter[str] = Counter()
    for comp in intel_report.get("similarity_vs_competitors") or []:
        pass

    return {
        "keywords": keywords,
        "search_queries": queries,
        "industry_terms": search.get("industry_terms") or [],
        "product_terms": search.get("product_terms") or [],
        "audience_terms": search.get("audience_terms") or [],
        "keyword_gaps": keyword_gaps[:10],
        "competitor_patterns": search.get("competitor_patterns") or [],
        "confidence": search.get("confidence"),
    }


def _marketing_strategy_section(
    *,
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    search_intelligence: dict[str, Any] | None,
    intel_report: dict[str, Any],
    market_insights: dict[str, Any],
) -> dict[str, Any]:
    profile = company_profile or {}
    analysis = company_analysis or {}
    search = search_intelligence or {}
    avg = intel_report.get("average_similarity") or {}

    user_ig = (analysis.get("user_instagram") or {}).get("instagram") or {}
    user_li = (analysis.get("user_linkedin") or {}).get("linkedin_analysis") or {}

    channels: list[str] = []
    if user_ig.get("username"):
        channels.append("instagram")
    if user_li or (analysis.get("user_linkedin") or {}).get("linkedin_url"):
        channels.append("linkedin")
    if profile.get("website"):
        channels.append("website")

    return {
        "positioning": profile.get("positioning") or profile.get("value_proposition"),
        "value_proposition": profile.get("value_proposition"),
        "target_audience": profile.get("target_audience") or [],
        "channels": channels,
        "audience_terms": search.get("audience_terms") or [],
        "dominant_market_themes": market_insights.get("dominant_themes") or [],
        "dominant_market_hashtags": market_insights.get("top_hashtags") or [],
        "marketing_similarity_avg": avg.get("marketing"),
        "b2b_positioning": user_li.get("b2b_positioning"),
        "thought_leadership_score": user_li.get("thought_leadership_score"),
    }


def _technology_section(
    *,
    company_profile: dict[str, Any],
    intel_report: dict[str, Any],
    gap_analysis: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    user_tech = company_profile.get("technologies") or []
    gaps = intel_report.get("gaps") or {}
    li_user = (intel_report.get("linkedin_analysis") or {}).get("user") or {}

    competitor_tech: Counter[str] = Counter()
    for comp in competitors:
        intel = comp.get("website_intelligence") or {}
        for tech in intel.get("technologies") or []:
            competitor_tech[str(tech).lower()] += 1
        for tech in (comp.get("linkedin_analysis") or {}).get("technologies_mentioned") or []:
            competitor_tech[str(tech).lower()] += 1

    return {
        "user_technologies": user_tech,
        "technologies_mentioned": li_user.get("technologies_mentioned") or [],
        "technology_gaps": gaps.get("technologies") or gap_analysis.get("technology_gaps") or [],
        "competitor_technologies": [
            {"technology": tech, "competitor_count": count}
            for tech, count in competitor_tech.most_common(12)
        ],
    }


def _content_strategy_section(
    *,
    company_analysis: dict[str, Any] | None,
    content_mix: list[dict[str, Any]],
    market_insights: dict[str, Any],
    intel_report: dict[str, Any],
) -> dict[str, Any]:
    analysis = company_analysis or {}
    user_ig = (analysis.get("user_instagram") or {}).get("instagram") or {}
    user_li = (analysis.get("user_linkedin") or {}).get("linkedin_analysis") or {}
    gaps = intel_report.get("gaps") or {}

    user_strategy = {
        "instagram": {
            "primary_format": user_ig.get("primary_format"),
            "primary_content_category": user_ig.get("primary_content_category"),
            "content_focus": user_ig.get("content_focus"),
            "media_mix": user_ig.get("media_mix") or [],
            "content_categories": user_ig.get("content_categories") or [],
            "top_hashtags": user_ig.get("top_hashtags") or [],
            "posting_frequency": user_ig.get("posting_frequency"),
            "avg_engagement_rate": user_ig.get("avg_engagement_rate"),
            "caption_style": user_ig.get("caption_style"),
        },
        "linkedin": {
            "content_themes": user_li.get("content_themes") or [],
            "post_count": user_li.get("post_count"),
            "thought_leadership_score": user_li.get("thought_leadership_score"),
        },
    }

    return {
        "user": user_strategy,
        "market": {
            "dominant_content_types": market_insights.get("dominant_content_types") or [],
            "dominant_themes": market_insights.get("dominant_themes") or [],
            "dominant_categories": market_insights.get("dominant_content_categories") or [],
            "top_hashtags": market_insights.get("top_hashtags") or [],
            "content_usage": market_insights.get("content_usage") or {},
        },
        "competitor_profiles": content_mix[:10],
        "content_type_gaps": gaps.get("content_types") or [],
    }


def _flatten_gaps(
    *,
    gap_analysis: dict[str, Any],
    intel_report: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    intel_gaps = intel_report.get("gaps") or {}

    for svc in intel_gaps.get("services") or gap_analysis.get("service_gaps") or []:
        label = svc if isinstance(svc, str) else svc.get("item", svc)
        items.append({"type": "service", "item": label, "priority": "high"})

    for tech in intel_gaps.get("technologies") or gap_analysis.get("technology_gaps") or []:
        label = tech if isinstance(tech, str) else tech.get("item", tech)
        items.append({"type": "technology", "item": label, "priority": "medium"})

    for row in intel_gaps.get("business_signals") or []:
        items.append(
            {
                "type": "business_signal",
                "item": row.get("signal"),
                "competitor_count": row.get("competitor_count"),
                "priority": "medium",
            }
        )

    for row in intel_gaps.get("content_types") or []:
        items.append(
            {
                "type": "content",
                "item": row.get("content_type"),
                "competitor_count": row.get("competitor_count"),
                "priority": "medium",
            }
        )

    for row in intel_gaps.get("review_platforms") or []:
        items.append(
            {
                "type": "review",
                "item": row.get("platform"),
                "competitor_count": row.get("competitor_count"),
                "priority": "high",
            }
        )

    for theme in gap_analysis.get("dominant_competitor_themes") or []:
        items.append(
            {
                "type": "theme",
                "item": theme.get("theme"),
                "competitor_count": theme.get("count"),
                "priority": "medium",
            }
        )

    return items[:30]


def _linkedin_section(
    *,
    company: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    intel_report: dict[str, Any],
) -> dict[str, Any]:
    social = company_analysis or {}
    user_li = social.get("user_linkedin") or {}
    intel_li = intel_report.get("linkedin_analysis") or {}
    intel_user = intel_li.get("user") or {}

    user_block = {
        "linkedin_url": user_li.get("linkedin_url") or company.get("linkedin_url"),
        "linkedin_posts_url": user_li.get("linkedin_posts_url") or social.get("linkedin_posts_url"),
        "skipped": user_li.get("skipped"),
        "analysis": user_li.get("linkedin_analysis") or user_li.get("analysis") or social.get("linkedin_analysis"),
        "content_themes": user_li.get("linkedin_content_themes") or social.get("linkedin_content_themes") or [],
        "posts": user_li.get("linkedin_posts") or social.get("linkedin_posts") or [],
        "employees": user_li.get("employees") or social.get("employees") or [],
        "employee_count": user_li.get("employee_count")
        or len(user_li.get("employees") or social.get("employees") or []),
        "job_openings": user_li.get("job_openings") or social.get("job_openings") or [],
        "company_size": user_li.get("company_size") or social.get("company_size"),
        "is_hiring": user_li.get("is_hiring") or social.get("is_hiring"),
        "hiring_signals": user_li.get("hiring_signals") or social.get("hiring_signals") or [],
        "warnings": user_li.get("warnings") or [],
        **{k: v for k, v in intel_user.items() if k not in {"analysis", "posts"}},
    }

    return {
        "user": user_block,
        "competitors": intel_li.get("competitors") or [],
    }


def _competitors_section(competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for comp in competitors:
        items.append(
            {
                "name": comp.get("name"),
                "username": comp.get("username"),
                "website": comp.get("website"),
                "linkedin_url": comp.get("linkedin_url"),
                "profile_url": comp.get("profile_url"),
                "followers": comp.get("followers"),
                "match_score": comp.get("match_score"),
                "similarity": comp.get("similarity"),
                "instagram": comp.get("instagram_analysis") or {},
                "linkedin": comp.get("linkedin_analysis") or {},
                "employees": (comp.get("employees") or [])[:20],
                "employee_count": comp.get("employee_count")
                or len(comp.get("employees") or []),
                "job_openings": comp.get("job_openings") or [],
                "company_size": comp.get("company_size"),
                "is_hiring": comp.get("is_hiring"),
                "warnings": comp.get("social_warnings") or [],
                "content_strategy": comp.get("content_strategy") or {},
                "posts": comp.get("posts") or [],
            }
        )
    return items


def _user_profile_section(
    *,
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    web_crawl: dict[str, Any] | None,
) -> dict[str, Any]:
    social = company_analysis or {}
    user_ig = social.get("user_instagram") or {}
    user_li = social.get("user_linkedin") or {}
    return {
        "company_understood": bool(company_profile.get("name")),
        "website_crawled": bool(web_crawl),
        "instagram_analyzed": not user_ig.get("skipped") and bool(
            user_ig.get("instagram") or social.get("instagram")
        ),
        "linkedin_analyzed": not user_li.get("skipped") and bool(
            user_li.get("linkedin_analysis") or user_li.get("analysis")
        ),
        "services": company_profile.get("services") or [],
        "technologies": company_profile.get("technologies") or [],
        "detected_niche": social.get("detected_niche") or user_ig.get("detected_niche"),
        "warnings": [
            *(user_ig.get("warnings") or []),
            *(user_li.get("warnings") or []),
        ],
    }


def build_analysis_sections(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any] | None,
    company_analysis: dict[str, Any] | None,
    competitor_intelligence_report: dict[str, Any] | None,
    gap_analysis: dict[str, Any] | None,
    search_intelligence: dict[str, Any] | None,
    web_crawl: dict[str, Any] | None,
    similarity_scores: list[dict] | None,
    recommendations: list[dict] | None,
    competitor_website_intel: list[dict] | None,
    content_mix: list[dict],
    market_insights: dict[str, Any],
    competitors: list[dict],
) -> dict[str, Any]:
    """Build the canonical analysis object expected by the API consumer."""
    profile = company_profile or {}
    intel = competitor_intelligence_report or {}
    gaps_raw = gap_analysis or {}
    social = company_analysis or {}

    user_ig_block = (social.get("user_instagram") or {})
    user_li_block = (social.get("user_linkedin") or {})

    return {
        "user_profile": _user_profile_section(
            company_profile=profile,
            company_analysis=company_analysis,
            web_crawl=web_crawl,
        ),
        "company": {
            "name": company.get("name") or profile.get("name"),
            "website": company.get("website") or profile.get("website"),
            "industry": profile.get("industry") or company.get("industry"),
            "description": profile.get("description"),
            "services": profile.get("services") or company.get("services") or [],
            "technologies": profile.get("technologies") or [],
            "target_audience": profile.get("target_audience") or [],
            "region": profile.get("region") or company.get("region"),
            "positioning": profile.get("positioning"),
            "value_proposition": profile.get("value_proposition"),
            "company_dna": social.get("company_dna") or {},
        },
        "website": {
            "url": company.get("website") or profile.get("website"),
            "intelligence": profile if profile.get("services") else {},
            "web_crawl": web_crawl or {},
            "competitor_sites": competitor_website_intel or [],
        },
        "instagram": {
            "scope": "user",
            "username": user_ig_block.get("username") or company.get("instagram_username"),
            "skipped": user_ig_block.get("skipped"),
            "analysis": user_ig_block.get("instagram") or user_ig_block.get("analysis") or social.get("instagram") or {},
            "posts": user_ig_block.get("posts") or social.get("instagram_posts") or social.get("company_posts") or [],
            "post_count": len(user_ig_block.get("posts") or social.get("instagram_posts") or []),
            "detected_niche": user_ig_block.get("detected_niche") or social.get("detected_niche"),
            "warnings": user_ig_block.get("warnings") or [],
        },
        "linkedin": {
            "scope": "user_and_competitors",
            **_linkedin_section(
                company=company,
                company_analysis=company_analysis,
                intel_report=intel,
            ),
        },
        "competitors": _competitors_section(competitors),
        "seo": _seo_section(
            company_profile=profile,
            search_intelligence=search_intelligence,
            web_crawl=web_crawl,
            gap_analysis=gaps_raw,
            intel_report=intel,
        ),
        "reviews": intel.get("review_intelligence") or {},
        "business_signals": intel.get("business_signals") or {},
        "content_strategy": _content_strategy_section(
            company_analysis=company_analysis,
            content_mix=content_mix,
            market_insights=market_insights,
            intel_report=intel,
        ),
        "marketing_strategy": _marketing_strategy_section(
            company_profile=profile,
            company_analysis=company_analysis,
            search_intelligence=search_intelligence,
            intel_report=intel,
            market_insights=market_insights,
        ),
        "technology": _technology_section(
            company_profile=profile,
            intel_report=intel,
            gap_analysis=gaps_raw,
            competitors=competitors,
        ),
        "swot": _swot_analysis(
            company_profile=profile,
            company_analysis=company_analysis,
            intel_report=intel,
            gap_analysis=gaps_raw,
            competitors=competitors,
        ),
        "similarity": {
            "average": intel.get("average_similarity") or {},
            "vs_competitors": intel.get("similarity_vs_competitors") or similarity_scores or [],
        },
        "gaps": _flatten_gaps(gap_analysis=gaps_raw, intel_report=intel),
        "recommendations": recommendations or [],
    }
