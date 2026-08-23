from __future__ import annotations
from typing import Any


def _who_is_beating_us(
    *,
    competitors_overview: dict[str, Any] | None,
    strategic_insights: dict[str, Any] | None,
    competitor_vs_company: dict[str, Any] | None,
    user_engagement: float | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    threats = (strategic_insights or {}).get("threats") or {}
    for item in threats.get("items") or []:
        name = str(item.get("competitor") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        rows.append(
            {
                "competitor": name,
                "reason": item.get("reason") or "Strong competitive signals",
                "dimension": "market_threat",
            }
        )

    for comp in (competitors_overview or {}).get("competitors") or []:
        name = str(comp.get("name") or comp.get("username") or "").strip()
        if not name or name.lower() in seen:
            continue
        engagement = float((comp.get("digital_presence") or {}).get("avg_engagement_rate") or 0)
        match_score = float(comp.get("match_score") or 0)
        reasons: list[str] = []
        if user_engagement is not None and engagement > user_engagement + 0.5:
            reasons.append(f"Higher Instagram engagement ({engagement}% vs yours)")
        if match_score >= 0.65:
            reasons.append("High market overlap on services and positioning")
        strengths = (comp.get("market_position_detail") or {}).get("strengths") or []
        if strengths:
            reasons.append(strengths[0])
        if not reasons:
            continue
        seen.add(name.lower())
        rows.append(
            {
                "competitor": name,
                "username": comp.get("username"),
                "match_score": comp.get("match_score"),
                "similarity_percentages": comp.get("similarity_percentages") or {},
                "reason": "; ".join(reasons[:2]),
                "dimension": "performance",
            }
        )

    comparison = competitor_vs_company or {}
    for row in comparison.get("competitor_advantages") or comparison.get("where_competitors_lead") or []:
        if isinstance(row, dict):
            name = str(row.get("competitor") or row.get("name") or "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                rows.append(
                    {
                        "competitor": name,
                        "reason": row.get("reason") or row.get("advantage") or "Leads on key dimensions",
                        "dimension": "comparison",
                    }
                )

    return rows[:8]


def _user_engagement(analysis: dict[str, Any] | None) -> float | None:
    ig = ((analysis or {}).get("instagram") or {}).get("analysis") or {}
    rate = ig.get("avg_engagement_rate")
    if rate is None:
        user_block = ((analysis or {}).get("instagram") or {})
        nested = user_block.get("analysis") or {}
        rate = nested.get("avg_engagement_rate")
    try:
        return float(rate) if rate is not None else None
    except (TypeError, ValueError):
        return None


def build_company_business_intelligence(
    *,
    overview: dict[str, Any] | None = None,
    competitors_overview: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    competitive_gaps: dict[str, Any] | None = None,
    content_intelligence: dict[str, Any] | None = None,
    market_insights: dict[str, Any] | None = None,
    hashtags: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    recommended_actions: list[Any] | None = None,
    growth_opportunities: list[Any] | None = None,
    competitor_report: dict[str, Any] | None = None,
    competitor_vs_company: dict[str, Any] | None = None,
    competitive_matchup: dict[str, Any] | None = None,
    summary: str | None = None,
    region: str | None = None,
    competitor_count: int = 0,
    post_count: int = 0,
) -> dict[str, Any]:
    """Build the 7-section user company business intelligence dashboard."""
    analysis = analysis or {}
    overview = overview or {}
    strategic = analysis.get("strategic_insights") or {}
    exec_summary = strategic.get("executive_summary") or {}
    linkedin = analysis.get("linkedin") or {}
    user_li = linkedin.get("user") or {}
    report = competitor_report or {}

    user_eng = _user_engagement(analysis)

    overview_section = {
        "title": "Overview",
        "question": "Where are we now?",
        "headline": overview.get("market_position"),
        "company_type": overview.get("company_type"),
        "region": region or overview.get("region"),
        "competitors_analyzed": competitor_count,
        "posts_analyzed": post_count,
        "digital_presence_score": (overview.get("digital_presence") or {}).get("score"),
        "digital_presence_label": (overview.get("digital_presence") or {}).get("label"),
        "key_insight": overview.get("key_insight"),
        "strengths": (overview.get("market_position_detail") or {}).get("strengths") or exec_summary.get("strengths") or [],
        "weaknesses": (overview.get("market_position_detail") or {}).get("weaknesses") or exec_summary.get("weaknesses") or [],
        "market_position": overview.get("market_position_detail") or {},
        "executive_score": exec_summary.get("score"),
        "biggest_opportunity": exec_summary.get("biggest_opportunity"),
        "biggest_threat": exec_summary.get("biggest_threat"),
        "summary": summary,
    }

    ninety_day = report.get("90_day_action_plan") or {}
    strategy_section = {
        "title": "Strategy",
        "question": "What should we change?",
        "key_insight": overview.get("key_insight"),
        "growth_opportunities": overview.get("growth_opportunities") or growth_opportunities or [],
        "recommended_actions": (report.get("11_recommended_actions") or {}).get("actions") or [],
        "strategic_opportunities": report.get("10_strategic_opportunities") or {},
        "ninety_day_action_plan": ninety_day,
        "swot": analysis.get("swot") or {},
        "priorities": {
            "high": (strategic.get("opportunities") or {}).get("high_priority") or [],
            "medium": (strategic.get("opportunities") or {}).get("medium_priority") or [],
        },
    }

    beating_us = _who_is_beating_us(
        competitors_overview=competitors_overview,
        strategic_insights=strategic,
        competitor_vs_company=competitor_vs_company,
        user_engagement=user_eng,
    )
    competitor_section = {
        "title": "Competitor",
        "question": "Who is beating us and why?",
        "who_we_compete_against": competitive_matchup or {},
        "competitors_outperforming": beating_us,
        "top_competitors": ((competitors_overview or {}).get("competitors") or [])[:5],
        "market_summary": (competitors_overview or {}).get("market_summary") or {},
        "competitive_gaps": competitive_gaps or {},
        "average_similarity": (analysis.get("similarity") or {}).get("average") or {},
        "threats": strategic.get("threats") or {},
        "growth_signals": strategic.get("growth_signals") or {},
    }

    li_analysis = user_li.get("analysis") or {}
    linkedin_section = {
        "title": "LinkedIn",
        "question": "How are we performing on LinkedIn?",
        "linkedin_url": user_li.get("linkedin_url"),
        "skipped": user_li.get("skipped"),
        "post_count": len(user_li.get("posts") or []),
        "employee_count": user_li.get("employee_count"),
        "is_hiring": user_li.get("is_hiring"),
        "company_size": user_li.get("company_size"),
        "content_themes": user_li.get("content_themes") or li_analysis.get("content_themes") or [],
        "thought_leadership_score": li_analysis.get("thought_leadership_score"),
        "b2b_positioning": li_analysis.get("b2b_positioning"),
        "technologies_mentioned": li_analysis.get("technologies_mentioned") or [],
        "hiring_signals": user_li.get("hiring_signals") or [],
        "competitor_linkedin_benchmark": (linkedin.get("competitors") or [])[:5],
        "performance_summary": _linkedin_performance_summary(user_li, linkedin.get("competitors") or []),
    }

    content_intel = content_intelligence or {}
    content_section = {
        "title": "Content",
        "question": "What content should we create?",
        "content_intelligence": content_intel,
        "top_topics_to_close": content_intel.get("top_topics") or [],
        "top_formats_to_close": content_intel.get("top_formats") or [],
        "content_opportunities": content_intel.get("content_opportunities") or [],
        "top_performing_topics": content_intel.get("top_performing_topics") or [],
        "top_performing_formats": content_intel.get("top_performing_formats") or [],
        "user_content_strategy": (analysis.get("content_strategy") or {}).get("user") or {},
        "market_content_patterns": (analysis.get("content_strategy") or {}).get("market") or market_insights or {},
        "posting_behavior": strategic.get("posting_behavior") or {},
        "recommendations": [
            rec for rec in (recommendations or [])
            if str(rec.get("type") or "").lower() in {"content", "format", "action"}
        ][:6],
    }

    hashtag_section = {
        "title": "Hashtag",
        "question": "How should we improve discoverability?",
        "top_market_hashtags": (market_insights or {}).get("top_hashtags") or [],
        "hashtag_summary": (market_insights or {}).get("hashtag_summary") or hashtags or [],
        "user_hashtags": (
            ((analysis.get("content_strategy") or {}).get("user") or {}).get("instagram") or {}
        ).get("top_hashtags") or [],
        "seo_gap": strategic.get("seo_gap") or {},
        "keyword_gaps": (analysis.get("seo") or {}).get("keyword_gaps") or [],
        "search_keywords": (analysis.get("seo") or {}).get("keywords") or [],
        "recommendations": _hashtag_recommendations(
            market_insights=market_insights,
            user_hashtags=(
                ((analysis.get("content_strategy") or {}).get("user") or {}).get("instagram") or {}
            ).get("top_hashtags") or [],
            strategic=strategic,
        ),
    }

    report_section = {
        "title": "Report",
        "question": "Give me the complete business intelligence report.",
        "section_index": report.get("section_index") or [],
        "executive_summary": report.get("01_executive_summary") or overview_section,
        "ninety_day_action_plan": ninety_day,
        "full_report": report,
        "download_ready": bool(report),
    }

    navigation = [
        {"key": "overview", "title": "Overview", "question": "Where are we now?"},
        {"key": "strategy", "title": "Strategy", "question": "What should we change?"},
        {"key": "competitor", "title": "Competitor", "question": "Who is beating us and why?"},
        {"key": "linkedin", "title": "LinkedIn", "question": "How are we performing on LinkedIn?"},
        {"key": "content", "title": "Content", "question": "What content should we create?"},
        {"key": "hashtag", "title": "Hashtag", "question": "How should we improve discoverability?"},
        {"key": "report", "title": "Report", "question": "Give me the complete business intelligence report."},
    ]

    return {
        "overview": overview_section,
        "strategy": strategy_section,
        "competitor": competitor_section,
        "linkedin": linkedin_section,
        "content": content_section,
        "hashtag": hashtag_section,
        "report": report_section,
        "navigation": navigation,
    }


def _linkedin_performance_summary(
    user: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> str:
    if user.get("skipped"):
        return "LinkedIn was not analyzed — connect your company LinkedIn URL for B2B performance insights."

    themes = user.get("content_themes") or []
    hiring = user.get("is_hiring")
    posts = len(user.get("posts") or [])
    comp_hiring = sum(1 for c in competitors if c.get("is_hiring"))

    parts: list[str] = []
    if posts:
        parts.append(f"You have {posts} LinkedIn posts in the analysis window.")
    elif themes:
        parts.append(f"LinkedIn content themes detected: {', '.join(str(t) for t in themes[:3])}.")
    else:
        parts.append("Limited LinkedIn content detected.")

    if hiring:
        parts.append("Your company shows active hiring signals.")
    if comp_hiring >= 2:
        parts.append(f"{comp_hiring} competitors are also actively hiring.")

    li_analysis = user.get("analysis") or {}
    if li_analysis.get("thought_leadership_score"):
        parts.append(f"Thought leadership score: {li_analysis['thought_leadership_score']}.")

    return " ".join(parts)


def _hashtag_recommendations(
    *,
    market_insights: dict[str, Any] | None,
    user_hashtags: list[Any],
    strategic: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    market_tags = [
        (row.get("tag") if isinstance(row, dict) else str(row))
        for row in (market_insights or {}).get("top_hashtags") or []
    ]
    user_set = {str(tag).lower().lstrip("#") for tag in user_hashtags if tag}

    missing = [tag for tag in market_tags[:8] if str(tag).lower().lstrip("#") not in user_set]
    if missing:
        recs.append(f"Adopt high-performing market hashtags: {', '.join(f'#{str(t).lstrip('#')}' for t in missing[:5])}.")

    for keyword in (strategic.get("seo_gap") or {}).get("missing_keywords") or []:
        recs.append(f"Target keyword in captions and hashtags: {keyword}.")

    if not recs:
        recs.append("Mix niche service hashtags with broader industry tags competitors use consistently.")
        recs.append("Pair each post with 3–5 targeted hashtags aligned to your primary service offering.")

    return recs[:6]
