"""Build the top-level company overview for competitor analysis responses."""

from __future__ import annotations

from typing import Any

from agents.analyzecompany.intelligence_context import clamp_score, intelligence_context
from service.Competitor.competitor_intelligence_report import (
    _competitor_lookup_key,
    _service_terms,
    _technology_terms,
)
from service.Competitor.linkedin_employees import competitor_linkedin_summary
from service.Competitor.signal_extractor import collect_text_blobs, extract_industries_targeted


def _clip(text: Any, limit: int = 240) -> str:
    value = " ".join(str(text or "").split()).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _company_type_from_ctx(ctx: dict[str, Any]) -> str:
    services_blob = " ".join(ctx["services"] + ctx["flagship"] + ctx["keywords"]).lower()
    industry = str(ctx.get("industry") or "").lower()
    if "ai" in services_blob or "llm" in services_blob or "genai" in services_blob:
        return "B2B AI Engineering Partner"
    if "staff augmentation" in services_blob or "resource" in services_blob:
        return "B2B IT Services / Staff Augmentation"
    if industry:
        return f"B2B {ctx['industry']} Company"
    return "B2B Technology Services"


def _market_position_label(ctx: dict[str, Any]) -> str:
    positioning = _clip(ctx.get("positioning") or "", 120)
    if positioning:
        lower = positioning.lower()
        if "ai-native" in lower or "ai native" in lower:
            return "AI-native engineering partner"
        return positioning
    if any("ai" in item.lower() for item in ctx["flagship"] + ctx["services"]):
        return "AI-native engineering partner"
    return "Specialist technology partner"


def _fallback_market_position(ctx: dict[str, Any]) -> dict[str, Any]:
    services = ctx["services"]
    flagship = ctx["flagship"]
    positioning = str(ctx.get("positioning") or "")
    ai_heavy = sum(1 for item in services + flagship if "ai" in item.lower() or "llm" in item.lower())
    category = "AI Software Engineering" if ai_heavy >= 2 or "ai" in positioning.lower() else (
        str(ctx.get("industry") or "Technology Services")
    )
    return {
        "category": category,
        "position": _market_position_label(ctx),
        "assessment": (
            "Strong technical breadth but positioning is broad."
            if len(services) >= 8
            else "Solid market presence with room to sharpen specialization."
        ),
    }


def _fallback_strengths(ctx: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    if any("ai" in item.lower() or "llm" in item.lower() for item in ctx["services"] + ctx["flagship"]):
        strengths.append("Strong AI/LLM positioning")
    if len(ctx["services"]) >= 6 or len(ctx["technologies"]) >= 6:
        strengths.append("Broad engineering capability")
    geo = " ".join(ctx["geography"] + ctx["keywords"] + ctx["audience"]).lower()
    if "gcc" in geo or "mena" in geo:
        strengths.append("Clear GCC/MENA focus")
    if not strengths:
        strengths.append("Foundational company DNA captured from available channels")
    return strengths[:6]


def _fallback_growth_opportunities(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    if len(ctx["services"]) >= 8:
        opportunities.append(
            {
                "area": "Positioning",
                "action": "Lead with your strongest niche capability instead of presenting all services equally.",
                "priority": "HIGH",
            }
        )
    if ctx.get("ig_followers") is not None and ctx["ig_followers"] < 1500:
        opportunities.append(
            {
                "area": "Social Growth",
                "action": "Increase publishing frequency and replicate high-engagement formats.",
                "priority": "HIGH",
            }
        )
    opportunities.append(
        {
            "area": "Proof",
            "action": "Publish case studies showing measurable business outcomes.",
            "priority": "MEDIUM",
        }
    )
    return opportunities[:5]


def _normalize_growth_opportunities(items: list[Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, str):
            if ":" in item:
                area, action = item.split(":", 1)
                rows.append({"area": area.strip(), "action": action.strip()})
            elif item.strip():
                rows.append({"area": "Growth", "action": item.strip()})
            continue
        if not isinstance(item, dict):
            continue
        action = item.get("action") or item.get("finding") or item.get("detail") or ""
        if not str(action).strip():
            continue
        rows.append(
            {
                "area": str(item.get("area") or item.get("category") or "Growth").strip(),
                "action": str(action).strip(),
                "priority": item.get("priority"),
            }
        )
    return rows[:6]


def _digital_presence_score(
    executive_snapshot: dict[str, Any] | None,
    digital_presence: dict[str, Any] | None,
) -> int | None:
    executive = executive_snapshot or {}
    digital = digital_presence or {}
    score = executive.get("overall_digital_presence_score")
    if score is None:
        score = digital.get("overall_score")
    if score is None:
        return None
    try:
        return clamp_score(float(score))
    except (TypeError, ValueError):
        return None


def _build_key_insight(
    *,
    market_position: dict[str, Any],
    summary: str | None,
    competitor_count: int,
    competitive_gaps: dict[str, Any] | None,
    content_intelligence: dict[str, Any] | None,
    competitor_intelligence_report: dict[str, Any] | None,
    growth_opportunities: list[dict[str, Any]],
) -> str:
    parts: list[str] = []

    assessment = market_position.get("assessment")
    if assessment:
        parts.append(str(assessment).strip())

    avg_similarity = (competitor_intelligence_report or {}).get("average_similarity") or {}
    overall = avg_similarity.get("overall")
    if overall is not None and competitor_count > 0:
        try:
            pct = round(float(overall) * 100)
            parts.append(
                f"Across {competitor_count} competitors, average similarity is {pct}% — "
                "differentiation will come from sharper positioning and proof."
            )
        except (TypeError, ValueError):
            pass

    service_gaps = (competitive_gaps or {}).get("service_gaps") or []
    if service_gaps:
        top = service_gaps[0]
        parts.append(
            f"Largest service gap: {top.get('service')} (used by {top.get('competitors_using', 0)} competitors)."
        )

    content_opps = (content_intelligence or {}).get("content_opportunities") or []
    if content_opps:
        row = content_opps[0]
        topic = row.get("topic")
        fmt = row.get("format")
        if topic and fmt:
            parts.append(f"Top content opportunity: {topic} content in {fmt} format.")

    if not parts and growth_opportunities:
        first = growth_opportunities[0]
        parts.append(f"{first.get('area')}: {first.get('action')}")

    if not parts and summary:
        sentence = summary.split(".")[0].strip()
        if sentence:
            parts.append(sentence + ".")

    if not parts:
        return (
            "Review market position, competitive gaps, and content intelligence below "
            "to prioritize positioning and social growth."
        )
    return " ".join(parts[:2])


def build_competitor_overview(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any] | None = None,
    company_analysis: dict[str, Any] | None = None,
    region: str | None = None,
    competitor_count: int = 0,
    post_count: int = 0,
    summary: str | None = None,
    executive_snapshot: dict[str, Any] | None = None,
    digital_presence: dict[str, Any] | None = None,
    market_position: dict[str, Any] | None = None,
    strengths_and_weaknesses: dict[str, Any] | None = None,
    growth_opportunities: list[Any] | None = None,
    competitive_gaps: dict[str, Any] | None = None,
    content_intelligence: dict[str, Any] | None = None,
    competitor_intelligence_report: dict[str, Any] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the company overview card shown at the top of competitor analysis."""
    profile = company_profile or company or {}
    ctx = intelligence_context(
        {
            "config": {"company": profile},
            "company_profile": profile,
            "company_analysis": company_analysis or {},
        }
    )

    executive = dict(executive_snapshot or {})
    market = dict(market_position or {})
    strengths_block = dict(strengths_and_weaknesses or {})

    if not executive:
        executive = {
            "company_type": _company_type_from_ctx(ctx),
            "market_position": _market_position_label(ctx),
            "overall_digital_presence_score": _digital_presence_score(None, digital_presence),
        }
    if not market:
        market = _fallback_market_position(ctx)

    strengths = list(strengths_block.get("strengths") or [])
    if not strengths:
        strengths = _fallback_strengths(ctx)

    growth_rows = _normalize_growth_opportunities(growth_opportunities)
    if not growth_rows:
        growth_rows = _fallback_growth_opportunities(ctx)
    if not growth_rows and recommendations:
        growth_rows = _normalize_growth_opportunities(
            [
                {
                    "area": item.get("category") or item.get("type") or "Strategy",
                    "action": item.get("title") or item.get("detail") or "",
                    "priority": item.get("priority"),
                }
                for item in recommendations[:4]
                if item.get("title") or item.get("detail")
            ]
        )

    digital_score = _digital_presence_score(executive, digital_presence)
    resolved_region = (
        region
        or profile.get("region")
        or ctx.get("region")
        or (company or {}).get("region")
        or "Not specified"
    )

    market_position_label = (
        executive.get("market_position")
        or market.get("position")
        or _market_position_label(ctx)
    )

    key_insight = _build_key_insight(
        market_position=market,
        summary=summary,
        competitor_count=competitor_count,
        competitive_gaps=competitive_gaps,
        content_intelligence=content_intelligence,
        competitor_intelligence_report=competitor_intelligence_report,
        growth_opportunities=growth_rows,
    )

    return {
        "market_position": market_position_label,
        "company_type": executive.get("company_type") or _company_type_from_ctx(ctx),
        "region": resolved_region,
        "competitors_analyzed": competitor_count,
        "posts_analyzed": post_count,
        "digital_presence": {
            "score": digital_score,
            "label": f"{digital_score}/100" if digital_score is not None else None,
            "channels": {
                "website": (digital_presence or {}).get("website") or {},
                "instagram": (digital_presence or {}).get("instagram") or {},
                "linkedin": (digital_presence or {}).get("linkedin") or {},
            },
        },
        "market_position_detail": {
            "category": market.get("category"),
            "position": market.get("position") or market_position_label,
            "specialization": market.get("specialization"),
            "geographic_focus": market.get("geographic_focus"),
            "enterprise_focus": market.get("enterprise_focus"),
            "assessment": market.get("assessment"),
            "strengths": strengths[:6],
            "weaknesses": list(strengths_block.get("weaknesses") or [])[:6],
        },
        "growth_opportunities": growth_rows,
        "key_insight": key_insight,
    }


def _lookup_raw_competitor(
    profile: dict[str, Any],
    raw_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    key = _competitor_lookup_key(profile)
    if key and key in raw_index:
        return raw_index[key]
    username = (profile.get("username") or "").strip().lstrip("@").lower()
    if username:
        for comp in raw_index.values():
            if (comp.get("username") or "").strip().lstrip("@").lower() == username:
                return comp
    name = (profile.get("name") or "").strip().lower()
    if name:
        for comp in raw_index.values():
            if (comp.get("name") or "").strip().lower() == name:
                return comp
    return {}


def _competitor_category(services: list[str], positioning: str) -> str:
    blob = " ".join(services).lower() + " " + positioning.lower()
    if "ai" in blob or "llm" in blob or "machine learning" in blob:
        return "AI Software Engineering"
    if "cloud" in blob or "devops" in blob:
        return "Cloud & DevOps Services"
    if "staff augmentation" in blob or "outsourcing" in blob:
        return "IT Staff Augmentation"
    if services:
        return services[0][:60]
    return "Technology Services"


def _competitor_company_type(services: list[str]) -> str:
    blob = " ".join(services).lower()
    if "ai" in blob or "llm" in blob:
        return "B2B AI Engineering Partner"
    if "staff augmentation" in blob:
        return "B2B IT Services / Staff Augmentation"
    return "B2B Technology Services"


def _competitor_strengths(
    *,
    services: list[str],
    technologies: list[str],
    strategy: dict[str, Any],
    raw: dict[str, Any],
) -> list[str]:
    strengths: list[str] = []
    service_blob = " ".join(services).lower()
    if "ai" in service_blob or "llm" in service_blob:
        strengths.append("Strong AI/LLM positioning")
    if len(services) >= 5:
        strengths.append("Broad engineering capability")
    geo_blob = collect_text_blobs(raw).lower()
    if "gcc" in geo_blob or "mena" in geo_blob:
        strengths.append("Clear GCC/MENA focus")
    industries = extract_industries_targeted(geo_blob)
    if industries:
        strengths.append(f"{industries[0].title()} vertical focus")
    if raw.get("is_hiring") or (raw.get("job_openings") or []):
        strengths.append("Active hiring signals")
    themes = strategy.get("themes") or []
    if themes:
        top = themes[0].get("theme") if isinstance(themes[0], dict) else themes[0]
        if top:
            strengths.append(f"Strong {top} content")
    if strategy.get("avg_engagement_rate", 0) >= 3:
        strengths.append("Above-average social engagement")
    if len(technologies) >= 4:
        strengths.append("Diverse technology stack")
    return list(dict.fromkeys(strengths))[:5]


def _competitor_key_insight(
    *,
    name: str,
    match_score: float | None,
    strategy: dict[str, Any],
    strengths: list[str],
    match_reasons: list[str],
) -> str:
    if match_reasons:
        return str(match_reasons[0]).strip()

    parts: list[str] = []
    label = name or "This competitor"
    if match_score is not None:
        try:
            pct = round(float(match_score) * 100)
            parts.append(f"{label} is a {pct}% match on services, tech, and content.")
        except (TypeError, ValueError):
            pass

    primary_format = strategy.get("primary_format")
    if primary_format:
        parts.append(f"Primary content format: {primary_format}.")

    if strengths:
        parts.append(f"Notable strength: {strengths[0]}.")

    return " ".join(parts[:2]) if parts else f"{label} is an active peer in your market."


def _competitor_overview_item(
    profile: dict[str, Any],
    *,
    raw: dict[str, Any],
    region: str | None,
) -> dict[str, Any]:
    intel = raw.get("website_intelligence") or profile.get("website_intelligence") or {}
    strategy = profile.get("content_strategy") or {}
    ig = profile.get("instagram_analysis") or raw.get("instagram_analysis") or {}
    li = profile.get("linkedin_analysis") or raw.get("linkedin_analysis") or {}

    services = list(dict.fromkeys(_service_terms({**raw, "website_intelligence": intel})))[:8]
    technologies = list(dict.fromkeys(_technology_terms({**raw, "website_intelligence": intel})))[:8]
    positioning = _clip(
        intel.get("positioning")
        or intel.get("value_proposition")
        or profile.get("bio")
        or raw.get("bio")
        or "",
        120,
    )
    category = _competitor_category(services, positioning)
    position = positioning or category
    if positioning and "ai-native" in positioning.lower():
        position = "AI-native engineering partner"
    elif not positioning and any("ai" in s.lower() for s in services):
        position = "AI-native engineering partner"

    strengths = _competitor_strengths(
        services=services,
        technologies=technologies,
        strategy=strategy,
        raw=raw,
    )
    match_score = profile.get("match_score")
    if match_score is None:
        match_score = (profile.get("similarity") or {}).get("overall")

    themes = [
        (row.get("theme") if isinstance(row, dict) else str(row))
        for row in (strategy.get("themes") or [])[:4]
        if row
    ]

    return {
        "name": profile.get("name") or raw.get("name"),
        "username": profile.get("username"),
        "website": profile.get("website") or raw.get("website"),
        "profile_url": profile.get("profile_url"),
        "profile_picture_url": profile.get("profile_picture_url"),
        "linkedin_url": profile.get("linkedin_url") or raw.get("linkedin_url"),
        "market_position": position,
        "company_type": _competitor_company_type(services),
        "region": region,
        "region_match": profile.get("region_match") or raw.get("region_match"),
        "niche_match": profile.get("niche_match") or raw.get("niche_match"),
        "match_score": match_score,
        "similarity_percentages": profile.get("similarity_percentages") or {},
        "digital_presence": {
            "instagram_followers": profile.get("followers") or ig.get("followers"),
            "avg_engagement_rate": strategy.get("avg_engagement_rate") or ig.get("avg_engagement_rate"),
            "primary_format": strategy.get("primary_format") or ig.get("primary_format"),
            "linkedin_present": bool(profile.get("linkedin_url") or raw.get("linkedin_url")),
            "website_present": bool(profile.get("website") or raw.get("website")),
            "linkedin_total_employees": profile.get("linkedin_total_employees") or raw.get("linkedin_total_employees"),
            "linkedin_company_size": profile.get("linkedin_company_size")
            or raw.get("linkedin_company_size")
            or profile.get("company_size")
            or raw.get("company_size"),
            "linkedin_employee_range": profile.get("linkedin_employee_range") or raw.get("linkedin_employee_range"),
            "linkedin_profiles_sampled": profile.get("linkedin_profiles_sampled")
            or raw.get("linkedin_profiles_sampled")
            or len(profile.get("employees") or raw.get("employees") or []),
        },
        "market_position_detail": {
            "category": category,
            "position": position,
            "services": services[:6],
            "technologies": technologies[:6],
            "strengths": strengths,
        },
        "content_highlights": {
            "post_count": strategy.get("post_count") or len(profile.get("posts") or []),
            "primary_format": strategy.get("primary_format"),
            "primary_content_category": strategy.get("primary_content_category"),
            "top_themes": themes,
            "avg_engagement_rate": strategy.get("avg_engagement_rate"),
            "best_performing_format": strategy.get("best_performing_format"),
        },
        "key_insight": _competitor_key_insight(
            name=profile.get("name") or raw.get("name") or profile.get("username") or "Competitor",
            match_score=float(match_score) if match_score is not None else None,
            strategy=strategy,
            strengths=strengths,
            match_reasons=list(profile.get("match_reasons") or raw.get("match_reasons") or [])[:3],
        ),
    }


def build_competitors_overview(
    *,
    competitor_profiles: list[dict[str, Any]],
    raw_competitors: list[dict[str, Any]] | None = None,
    region: str | None = None,
    post_count: int = 0,
    competitor_intelligence_report: dict[str, Any] | None = None,
    market_insights: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build per-competitor overview cards plus a short market summary."""
    raw_index: dict[str, dict[str, Any]] = {}
    for comp in raw_competitors or []:
        key = _competitor_lookup_key(comp)
        if key:
            raw_index[key] = comp

    items = [
        _competitor_overview_item(
            profile,
            raw=_lookup_raw_competitor(profile, raw_index),
            region=region,
        )
        for profile in competitor_profiles
    ]
    items.sort(
        key=lambda row: float(row.get("match_score") or 0),
        reverse=True,
    )

    match_scores = [float(row["match_score"]) for row in items if row.get("match_score") is not None]
    avg_match = round(sum(match_scores) / len(match_scores), 3) if match_scores else None

    market = market_insights or {}
    linkedin_stats = competitor_linkedin_summary(raw_competitors or competitor_profiles)
    return {
        "total_competitors": len(items),
        "posts_analyzed": post_count,
        "region": region,
        "market_summary": {
            "avg_match_score": avg_match,
            "avg_match_score_pct": round(avg_match * 100) if avg_match is not None else None,
            "dominant_formats": market.get("dominant_content_types") or [],
            "dominant_themes": market.get("dominant_themes") or [],
            "dominant_categories": market.get("dominant_content_categories") or [],
            **linkedin_stats,
        },
        "competitors": items,
    }
