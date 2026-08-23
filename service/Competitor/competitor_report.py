"""Structured competitor analysis report (11 sections + 90-day action plan)."""

from __future__ import annotations

from typing import Any


def _action_item(
    *,
    title: str,
    action: str,
    category: str = "Strategy",
    priority: str = "medium",
    impact: str = "Medium",
    effort: str = "Medium",
    timeline: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "action": action,
        "category": category,
        "priority": priority.lower(),
        "impact": impact,
        "effort": effort,
        "timeline": timeline,
    }


def _normalize_actions(items: list[Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, str):
            if item.strip():
                rows.append(_action_item(title="Recommended action", action=item.strip()))
            continue
        if not isinstance(item, dict):
            continue
        action = (
            item.get("action")
            or item.get("detail")
            or item.get("title")
            or ""
        )
        if not str(action).strip():
            continue
        rows.append(
            _action_item(
                title=str(item.get("title") or item.get("area") or "Recommended action"),
                action=str(action).strip(),
                category=str(item.get("category") or item.get("type") or item.get("area") or "Strategy"),
                priority=str(item.get("priority") or "medium").lower(),
                impact=str(item.get("impact") or "Medium"),
                effort=str(item.get("effort") or "Medium"),
            )
        )
    return rows


def _build_90_day_action_plan(
    *,
    recommended_actions: list[Any] | None,
    recommendations: list[dict[str, Any]] | None,
    growth_opportunities: list[Any] | None,
    strategic_opportunities: dict[str, Any] | None,
    competitive_gaps: dict[str, Any] | None,
    content_intelligence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Phase prioritized actions into 0-30, 31-60, and 61-90 day buckets."""
    pool: list[dict[str, Any]] = []

    pool.extend(_normalize_actions(recommended_actions))
    pool.extend(_normalize_actions(recommendations))
    pool.extend(_normalize_actions(growth_opportunities))

    opp = strategic_opportunities or {}
    for label in opp.get("high_priority") or opp.get("high") or []:
        if isinstance(label, str) and label.strip():
            pool.append(_action_item(title="Strategic opportunity", action=label.strip(), priority="high"))
    for label in opp.get("medium_priority") or opp.get("medium") or []:
        if isinstance(label, str) and label.strip():
            pool.append(_action_item(title="Strategic opportunity", action=label.strip(), priority="medium"))

    for row in (content_intelligence or {}).get("content_opportunities") or []:
        topic = row.get("topic")
        fmt = row.get("format")
        if topic and fmt:
            pool.append(
                _action_item(
                    title=f"Content: {topic}",
                    action=f"Publish {topic} content using {fmt} format.",
                    category="Content",
                    priority=str(row.get("priority") or "medium"),
                )
            )

    for row in (competitive_gaps or {}).get("service_gaps") or []:
        if row.get("priority") == "high" and row.get("service"):
            pool.append(
                _action_item(
                    title=f"Close service gap: {row['service']}",
                    action=f"Evaluate offering or positioning for {row['service']} used by {row.get('competitors_using', 0)} competitors.",
                    category="Services",
                    priority="high",
                )
            )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in pool:
        key = (row.get("title", "").lower(), row.get("action", "").lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    deduped.sort(key=lambda row: priority_rank.get(str(row.get("priority") or "medium"), 9))

    days_0_30: list[dict[str, Any]] = []
    days_31_60: list[dict[str, Any]] = []
    days_61_90: list[dict[str, Any]] = []

    for idx, row in enumerate(deduped[:12]):
        item = {**row, "timeline": "0-30 days" if idx < 4 else ("31-60 days" if idx < 8 else "61-90 days")}
        if idx < 4:
            days_0_30.append(item)
        elif idx < 8:
            days_31_60.append(item)
        else:
            days_61_90.append(item)

    if not days_0_30:
        days_0_30 = [
            _action_item(
                title="Sharpen positioning",
                action="Lead with your strongest niche capability in website and social bios.",
                category="Positioning",
                priority="high",
                timeline="0-30 days",
            )
        ]
    if not days_31_60:
        days_31_60 = [
            _action_item(
                title="Increase content velocity",
                action="Publish weekly educational content aligned with top competitor themes.",
                category="Content",
                priority="medium",
                timeline="31-60 days",
            )
        ]
    if not days_61_90:
        days_61_90 = [
            _action_item(
                title="Build proof assets",
                action="Publish case studies with measurable business outcomes.",
                category="Proof",
                priority="medium",
                timeline="61-90 days",
            )
        ]

    return {
        "summary": (
            f"{len(days_0_30)} immediate actions, {len(days_31_60)} mid-term initiatives, "
            f"and {len(days_61_90)} longer-term moves over the next 90 days."
        ),
        "days_0_30": days_0_30,
        "days_31_60": days_31_60,
        "days_61_90": days_61_90,
        "all_actions": days_0_30 + days_31_60 + days_61_90,
    }


def build_competitor_report(
    *,
    summary: str | None = None,
    overview: dict[str, Any] | None = None,
    competitors_overview: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    competitive_gaps: dict[str, Any] | None = None,
    quantified_competitive_gaps: dict[str, Any] | None = None,
    content_intelligence: dict[str, Any] | None = None,
    market_insights: dict[str, Any] | None = None,
    hashtags: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    recommended_actions: list[Any] | None = None,
    growth_opportunities: list[Any] | None = None,
    digital_presence: dict[str, Any] | None = None,
    executive_snapshot: dict[str, Any] | None = None,
    market_position: dict[str, Any] | None = None,
    positioning_analysis: dict[str, Any] | None = None,
    strengths_and_weaknesses: dict[str, Any] | None = None,
    competitor_count: int = 0,
    post_count: int = 0,
    region: str | None = None,
) -> dict[str, Any]:
    """Build the numbered competitor analysis report sections."""
    analysis = analysis or {}
    overview = overview or {}
    strategic = analysis.get("strategic_insights") or {}
    exec_block = strategic.get("executive_summary") or {}
    company = analysis.get("company") or {}
    linkedin = analysis.get("linkedin") or {}
    content_strategy = analysis.get("content_strategy") or {}

    executive_summary = {
        "summary_text": summary or "",
        "key_insight": overview.get("key_insight"),
        "score": exec_block.get("score"),
        "strengths": exec_block.get("strengths") or (overview.get("market_position_detail") or {}).get("strengths") or [],
        "weaknesses": exec_block.get("weaknesses") or (overview.get("market_position_detail") or {}).get("weaknesses") or [],
        "biggest_opportunity": exec_block.get("biggest_opportunity"),
        "biggest_threat": exec_block.get("biggest_threat"),
        "competitors_analyzed": competitor_count,
        "posts_analyzed": post_count,
        "region": region or overview.get("region"),
    }

    company_position = {
        "company_name": company.get("name") or overview.get("company_type"),
        "company_type": overview.get("company_type") or (executive_snapshot or {}).get("company_type"),
        "market_position": overview.get("market_position"),
        "positioning": company.get("positioning") or (positioning_analysis or {}).get("recommended_positioning"),
        "value_proposition": company.get("value_proposition"),
        "core_offering": (executive_snapshot or {}).get("core_offering"),
        "primary_market": (executive_snapshot or {}).get("primary_market") or region,
        "primary_customers": (executive_snapshot or {}).get("primary_customers") or company.get("target_audience") or [],
        "services": company.get("services") or [],
        "technologies": company.get("technologies") or [],
        "what_you_are_known_for": (positioning_analysis or {}).get("what_you_are_known_for") or [],
        "what_is_unclear": (positioning_analysis or {}).get("what_is_unclear") or [],
    }

    digital = digital_presence or overview.get("digital_presence") or {}
    digital_presence_section = {
        "overall_score": digital.get("score") or digital.get("overall_score") or (executive_snapshot or {}).get("overall_digital_presence_score"),
        "label": (overview.get("digital_presence") or {}).get("label"),
        "website": digital.get("channels", {}).get("website") if isinstance(digital.get("channels"), dict) else digital.get("website") or {},
        "instagram": digital.get("channels", {}).get("instagram") if isinstance(digital.get("channels"), dict) else digital.get("instagram") or {},
        "linkedin": digital.get("channels", {}).get("linkedin") if isinstance(digital.get("channels"), dict) else digital.get("linkedin") or {},
        "user_instagram": analysis.get("instagram") or {},
    }

    market_position_section = {
        **(market_position or {}),
        **(overview.get("market_position_detail") or {}),
        "position": overview.get("market_position") or (market_position or {}).get("position"),
        "category": (market_position or {}).get("category") or (overview.get("market_position_detail") or {}).get("category"),
        "strategic_market_position": strategic.get("market_position") or {},
        "strengths_and_weaknesses": strengths_and_weaknesses or {},
    }

    competitor_landscape = {
        "total_competitors": competitor_count,
        "region": region or overview.get("region"),
        "market_summary": (competitors_overview or {}).get("market_summary") or {},
        "competitors": (competitors_overview or {}).get("competitors") or [],
        "similarity": analysis.get("similarity") or {},
        "competitor_profiles": analysis.get("competitors") or [],
    }

    competitive_gaps_section = {
        "niche_gaps": competitive_gaps or {},
        "quantified_gaps": quantified_competitive_gaps or {},
        "legacy_gaps": analysis.get("gaps") or [],
        "missing_services": strategic.get("missing_services") or {},
        "technology_gap": strategic.get("technology_gap") or {},
        "content_gap": strategic.get("content_gap") or {},
    }

    linkedin_analysis = {
        "user": linkedin.get("user") or {},
        "competitors": linkedin.get("competitors") or [],
        "summary": {
            "user_post_count": len((linkedin.get("user") or {}).get("posts") or []),
            "competitor_profiles": len(linkedin.get("competitors") or []),
            "is_hiring": (linkedin.get("user") or {}).get("is_hiring"),
            "employee_count": (linkedin.get("user") or {}).get("employee_count"),
        },
    }

    content_analysis = {
        "content_intelligence": content_intelligence or {},
        "user_strategy": content_strategy.get("user") or {},
        "market_patterns": content_strategy.get("market") or market_insights or {},
        "competitor_content_profiles": content_strategy.get("competitor_profiles") or [],
        "strategic_content_strategy": strategic.get("content_strategy") or {},
        "posting_behavior": strategic.get("posting_behavior") or {},
    }

    hashtag_analysis = {
        "top_hashtags": (market_insights or {}).get("top_hashtags") or [],
        "hashtag_summary": (market_insights or {}).get("hashtag_summary") or hashtags or [],
        "dominant_market_hashtags": (analysis.get("marketing_strategy") or {}).get("dominant_market_hashtags") or [],
        "user_top_hashtags": ((content_strategy.get("user") or {}).get("instagram") or {}).get("top_hashtags") or [],
    }

    opportunities = strategic.get("opportunities") or {}
    strategic_opportunities = {
        "high_priority": opportunities.get("high") or opportunities.get("high_priority") or [],
        "medium_priority": opportunities.get("medium") or opportunities.get("medium_priority") or [],
        "growth_opportunities": overview.get("growth_opportunities") or growth_opportunities or [],
        "content_opportunities": (content_intelligence or {}).get("content_opportunities") or [],
        "swot_opportunities": (analysis.get("swot") or {}).get("opportunities") or [],
        "seo_gap": strategic.get("seo_gap") or {},
    }

    all_recommendations = _normalize_actions(recommended_actions)
    all_recommendations.extend(_normalize_actions(recommendations))
    all_recommendations.extend(_normalize_actions(growth_opportunities))

    seen_rec: set[tuple[str, str]] = set()
    deduped_recs: list[dict[str, Any]] = []
    for row in all_recommendations:
        key = (row.get("title", "").lower(), row.get("action", "").lower())
        if key in seen_rec:
            continue
        seen_rec.add(key)
        deduped_recs.append(row)

    recommended_actions_section = {
        "actions": deduped_recs[:15],
        "pipeline_recommendations": recommendations or [],
        "analyze_company_actions": recommended_actions or [],
    }

    ninety_day_plan = _build_90_day_action_plan(
        recommended_actions=recommended_actions,
        recommendations=recommendations,
        growth_opportunities=growth_opportunities or overview.get("growth_opportunities"),
        strategic_opportunities=opportunities,
        competitive_gaps=competitive_gaps,
        content_intelligence=content_intelligence,
    )

    sections = {
        "01_executive_summary": executive_summary,
        "02_company_position": company_position,
        "03_digital_presence": digital_presence_section,
        "04_market_position": market_position_section,
        "05_competitor_landscape": competitor_landscape,
        "06_competitive_gaps": competitive_gaps_section,
        "07_linkedin_analysis": linkedin_analysis,
        "08_content_analysis": content_analysis,
        "09_hashtag_analysis": hashtag_analysis,
        "10_strategic_opportunities": strategic_opportunities,
        "11_recommended_actions": recommended_actions_section,
    }

    return {
        **sections,
        "90_day_action_plan": ninety_day_plan,
        "section_index": [
            {"id": "01", "key": "executive_summary", "title": "Executive Summary"},
            {"id": "02", "key": "company_position", "title": "Company Position"},
            {"id": "03", "key": "digital_presence", "title": "Digital Presence"},
            {"id": "04", "key": "market_position", "title": "Market Position"},
            {"id": "05", "key": "competitor_landscape", "title": "Competitor Landscape"},
            {"id": "06", "key": "competitive_gaps", "title": "Competitive Gaps"},
            {"id": "07", "key": "linkedin_analysis", "title": "LinkedIn Analysis"},
            {"id": "08", "key": "content_analysis", "title": "Content Analysis"},
            {"id": "09", "key": "hashtag_analysis", "title": "Hashtag Analysis"},
            {"id": "10", "key": "strategic_opportunities", "title": "Strategic Opportunities"},
            {"id": "11", "key": "recommended_actions", "title": "Recommended Actions"},
            {"id": "90", "key": "90_day_action_plan", "title": "90-Day Action Plan"},
        ],
    }
