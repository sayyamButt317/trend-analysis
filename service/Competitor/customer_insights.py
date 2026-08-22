from __future__ import annotations
from collections import Counter
from typing import Any
from service.Competitor.gap_filters import clean_gap_terms, is_meaningful_gap_term

_KNOWN_SERVICE_HINTS = (
    "cloud", "ai", "devops", "staff", "mobile", "web", "data", "qa", "security",
    "automation", "software", "consulting", "migration", "development", "design",
    "marketing", "analytics", "machine learning", "ml", "genai", "generative",
)
_DIMENSION_LABELS = {
    "services": "Same services",
    "technology": "Similar tech stack",
    "tech": "Similar tech stack",
    "marketing": "Similar marketing",
    "content": "Similar content strategy",
    "location": "Same geography",
    "target_audience": "Same customer segment",
    "industry": "Same industry",
    "pricing": "Similar pricing",
    "social_strategy": "Similar social strategy",
}


def _similarity_to_percentages(similarity: dict[str, Any]) -> dict[str, int]:
    from service.Competitor.competitor_intelligence_report import similarity_to_percentages

    return similarity_to_percentages(similarity)


def _service_terms(entity: dict[str, Any]) -> list[str]:
    from service.Competitor.competitor_intelligence_report import _service_terms as _terms

    return _terms(entity)


def _title(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return text
    acronyms = {"ai", "ml", "qa", "ui", "ux", "seo", "api", "aws", "gcp", "b2b", "saas"}
    return " ".join(
        part.upper() if part.lower() in acronyms else part.capitalize()
        for part in text.replace("_", " ").split()
    )


def _pct(value: float | int | None) -> int:
    return max(0, min(100, int(round(float(value or 0)))))


def _comp_name(comp: dict[str, Any]) -> str:
    return str(comp.get("name") or comp.get("username") or "Competitor").strip()


def _similarity_blob(comp: dict[str, Any]) -> dict[str, Any]:
    return dict(comp.get("similarity") or {})


def _similarity_percent(comp: dict[str, Any]) -> int:
    pcts = comp.get("similarity_percentages") or {}
    if pcts.get("overall") is not None:
        return _pct(pcts.get("overall"))
    sim = _similarity_blob(comp)
    if sim.get("overall") is not None:
        overall = float(sim["overall"])
        return _pct(overall * 100 if overall <= 1 else overall)
    match = float(comp.get("match_score") or 0)
    return _pct(match * 100 if match <= 1 else match)


def _why_similar(comp: dict[str, Any]) -> str:
    sim = _similarity_blob(comp)
    pcts = comp.get("similarity_percentages") or _similarity_to_percentages(sim)
    ranked: list[tuple[str, int]] = []
    for key, label in _DIMENSION_LABELS.items():
        score = pcts.get(key)
        if score is None and key in sim:
            raw = float(sim.get(key) or 0)
            score = raw * 100 if raw <= 1 else raw
        if score is None:
            continue
        score_i = _pct(score)
        if score_i >= 45:
            ranked.append((label, score_i))
    ranked.sort(key=lambda item: item[1], reverse=True)
    if ranked:
        return " + ".join(label for label, _ in ranked[:3])
    reasons = [str(r) for r in (comp.get("match_reasons") or []) if r]
    if reasons:
        return "; ".join(reasons[:2])
    explanation = str(sim.get("explanation") or "").strip()
    return explanation[:160] if explanation else "Overlapping market presence"


def _user_services(company: dict[str, Any], profile: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for source in (profile.get("services") or [], company.get("services") or []):
        for item in source:
            if item and is_meaningful_gap_term(item):
                terms.add(str(item).lower().strip())
    return terms


def _user_has_service(user_services: set[str], term: str) -> bool:
    key = term.lower().strip()
    if key in user_services:
        return True
    return any(key in own or own in key for own in user_services)


def _service_frequency(competitors: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for comp in competitors:
        seen: set[str] = set()
        for term in _service_terms(comp):
            key = str(term).lower().strip()
            if not is_meaningful_gap_term(key) or key in seen:
                continue
            if " " not in key and not any(hint in key for hint in _KNOWN_SERVICE_HINTS):
                continue
            seen.add(key)
            counts[key] += 1
    return counts


def _theme_frequency(
    competitors: list[dict[str, Any]],
    content_mix: list[dict[str, Any]],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for profile in content_mix:
        for row in profile.get("content_themes") or profile.get("themes") or []:
            theme = str((row.get("theme") if isinstance(row, dict) else row) or "").strip()
            if is_meaningful_gap_term(theme) and theme.lower() != "general":
                counts[theme.lower()] += int((row.get("count") if isinstance(row, dict) else 1) or 1)
        for row in profile.get("content_categories") or []:
            cat = str((row.get("category") if isinstance(row, dict) else row) or "").strip()
            if is_meaningful_gap_term(cat) and cat.lower() != "general":
                counts[cat.lower()] += int((row.get("count") if isinstance(row, dict) else 1) or 1)
    for comp in competitors:
        strategy = comp.get("content_strategy") or {}
        for row in strategy.get("themes") or strategy.get("content_themes") or []:
            theme = str((row.get("theme") if isinstance(row, dict) else row) or "").strip()
            if is_meaningful_gap_term(theme) and theme.lower() != "general":
                counts[theme.lower()] += 1
        li = comp.get("linkedin_analysis") or {}
        for theme in li.get("content_themes") or []:
            if is_meaningful_gap_term(theme):
                counts[str(theme).lower()] += 1
    return counts


def _build_real_competitors(competitors: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(competitors, key=_similarity_percent, reverse=True)
    rows = []
    for comp in ranked[:10]:
        rows.append(
            {
                "competitor": _comp_name(comp),
                "username": comp.get("username"),
                "website": comp.get("website"),
                "similarity": _similarity_percent(comp),
                "why": _why_similar(comp),
                "dimensions": comp.get("similarity_percentages")
                or _similarity_to_percentages(_similarity_blob(comp)),
            }
        )
    return {
        "question": "Who are my real competitors?",
        "summary": (
            f"Identified {len(rows)} competitors ranked by multi-dimension similarity "
            "(services, audience, geography, tech, content)."
            if rows
            else "No competitors available yet."
        ),
        "competitors": rows,
    }


def _build_competitive_strengths(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    competitors: list[dict[str, Any]],
    gap_analysis: dict[str, Any],
    intel_report: dict[str, Any],
) -> dict[str, Any]:
    total = max(len(competitors), 1)
    user_services = _user_services(company, company_profile)
    freq = _service_frequency(competitors)
    strengths: list[dict[str, Any]] = []

    for term, count in freq.most_common(20):
        if _user_has_service(user_services, term):
            continue
        if count < max(1, total // 4) and count < 2:
            continue
        strengths.append(
            {
                "area": _title(term),
                "competitors_promoting": count,
                "market_share": _pct((count / total) * 100),
                "you": "Not detected",
            }
        )
        if len(strengths) >= 8:
            break

    tl_count = sum(
        1
        for comp in competitors
        if float((comp.get("linkedin_analysis") or {}).get("thought_leadership_score") or 0) >= 0.45
        or "thought" in " ".join(
            str(t).lower() for t in ((comp.get("linkedin_analysis") or {}).get("content_themes") or [])
        )
    )
    if tl_count >= 2:
        strengths.append(
            {
                "area": "Thought Leadership",
                "competitors_promoting": tl_count,
                "market_share": _pct((tl_count / total) * 100),
                "you": "Limited or not detected",
            }
        )

    if len(strengths) < 4:
        for term in clean_gap_terms(gap_analysis.get("service_gaps"), limit=8):
            if any(s["area"].lower() == term.lower() for s in strengths):
                continue
            strengths.append(
                {
                    "area": _title(term),
                    "competitors_promoting": None,
                    "market_share": None,
                    "you": "Not detected",
                }
            )
            if len(strengths) >= 6:
                break

    return {
        "question": "What are competitors doing better than me?",
        "summary": (
            "Competitors outperform you in these promoted areas."
            if strengths
            else "Your promoted service coverage looks aligned with competitors."
        ),
        "strengths": strengths[:8],
    }


def _build_opportunity_gaps(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    competitors: list[dict[str, Any]],
    gap_analysis: dict[str, Any],
    intel_report: dict[str, Any],
) -> dict[str, Any]:
    total = max(len(competitors), 1)
    user_services = _user_services(company, company_profile)
    freq = _service_frequency(competitors)

    for row in (intel_report.get("gaps") or {}).get("services") or []:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item") or "").lower().strip()
        if not is_meaningful_gap_term(item):
            continue
        count = int(row.get("competitor_count") or 0)
        if count > freq[item]:
            freq[item] = count

    opportunities: list[dict[str, Any]] = []
    for term, count in freq.most_common(25):
        if _user_has_service(user_services, term):
            status = "Available but under-promoted"
            if count < max(2, total // 3):
                continue
            opportunity = "Medium"
        else:
            status = "Not detected"
            if count >= max(3, int(total * 0.5)):
                opportunity = "High"
            elif count >= 2:
                opportunity = "Medium"
            else:
                continue
        opportunities.append(
            {
                "opportunity": opportunity,
                "area": _title(term),
                "promoted_by": f"{count}/{total} competitors",
                "competitor_count": count,
                "you": status,
            }
        )
        if len(opportunities) >= 8:
            break

    if not opportunities:
        for term in clean_gap_terms(
            (intel_report.get("gaps") or {}).get("services") or gap_analysis.get("service_gaps"),
            limit=6,
        ):
            opportunities.append(
                {
                    "opportunity": "Medium",
                    "area": _title(term),
                    "promoted_by": "Competitors promote this",
                    "competitor_count": None,
                    "you": "Not detected",
                }
            )

    high = sum(1 for item in opportunities if item["opportunity"] == "High")
    return {
        "question": "Where are my opportunities?",
        "summary": (
            f"{high} high-opportunity gaps and {len(opportunities)} total opportunities vs the competitive set."
            if opportunities
            else "No clear service gaps stood out against competitors."
        ),
        "gaps": opportunities,
    }


def _build_market_positioning(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    competitors: list[dict[str, Any]],
    intel_report: dict[str, Any],
    market_position: dict[str, Any] | None,
) -> dict[str, Any]:
    position = market_position or {}
    your_score = _pct(
        position.get("market_percentile")
        or ((intel_report.get("average_similarity") or {}).get("overall") or 0) * 100
    )
    scores = sorted((_similarity_percent(comp) for comp in competitors), reverse=True)
    leader = scores[0] if scores else max(your_score + 8, 90)
    strong = scores[1] if len(scores) > 1 else max(your_score + 4, min(leader - 4, 84))
    emerging = scores[-1] if scores else max(40, your_score - 15)

    ladder = [
        {"label": "Leader", "score": _pct(leader), "is_you": False},
        {"label": "Strong", "score": _pct(strong), "is_you": False},
        {"label": "You", "score": your_score, "is_you": True},
        {"label": "Emerging", "score": _pct(emerging), "is_you": False},
    ]

    user_services = [_title(s) for s in (company_profile.get("services") or company.get("services") or [])[:6]]
    ai_native = any("ai" in s.lower() for s in user_services)
    differentiation = (
        "Most competitors position around general software development. "
        "Your strongest opportunity is to own AI-native software development + AI automation."
        if ai_native
        else (
            "Most competitors position broadly across software services. "
            f"Differentiate by owning {', '.join(user_services[:2]) or 'a focused specialty'} "
            "with clearer proof (case studies + measurable outcomes)."
        )
    )

    return {
        "question": "How should I position myself?",
        "position_label": position.get("position_label") or "Competitive Peer",
        "similarity_to_market": your_score,
        "ladder": ladder,
        "differentiation_opportunity": differentiation,
        "service_coverage": position.get("service_coverage"),
        "technology_coverage": position.get("technology_coverage"),
        "brand_visibility": position.get("brand_visibility"),
        "engagement_vs_market": position.get("engagement_vs_market"),
    }


def _build_content_opportunity(
    *,
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
    content_mix: list[dict[str, Any]],
    gap_analysis: dict[str, Any],
) -> dict[str, Any]:
    themes = _theme_frequency(competitors, content_mix)
    formats: Counter[str] = Counter()
    for profile in content_mix:
        for row in profile.get("media_types") or []:
            fmt = str((row.get("type") if isinstance(row, dict) else row) or "").strip()
            if is_meaningful_gap_term(fmt):
                formats[fmt.lower()] += int((row.get("count") if isinstance(row, dict) else 1) or 1)
    for row in gap_analysis.get("dominant_competitor_formats") or []:
        fmt = str((row.get("format") if isinstance(row, dict) else row) or "").strip()
        if is_meaningful_gap_term(fmt):
            formats[fmt.lower()] += int((row.get("count") if isinstance(row, dict) else 1) or 1)

    winning = [_title(theme) for theme, _ in themes.most_common(6)]
    if not winning:
        winning = [
            _title(str(row.get("theme") or ""))
            for row in (gap_analysis.get("dominant_competitor_themes") or [])[:5]
            if is_meaningful_gap_term(row.get("theme"))
        ]

    experiments: list[str] = []
    lower_winning = " ".join(winning).lower()
    if "thought" in lower_winning or "leadership" in lower_winning:
        experiments.append("Founder POV / thought-leadership posts")
    if "case" in lower_winning or "success" in lower_winning:
        experiments.append("Client case studies with outcomes")
    if "ai" in lower_winning:
        experiments.append("AI industry insights and explainers")
    if formats.get("reels") or formats.get("video") or formats.get("reel"):
        experiments.append("Short-form educational videos")
    if not experiments:
        experiments = [
            "Technical explainers",
            "Client case studies",
            "Short-form educational videos",
            "Founder POV",
        ]
    else:
        for item in ("Technical explainers", "Client case studies", "Short-form educational videos"):
            if item not in experiments:
                experiments.append(item)

    user_ig = ((company_analysis or {}).get("user_instagram") or {}).get("instagram") or {}
    return {
        "question": "What content should I create?",
        "summary": "Competitors are winning with these content themes — use them as experiments, not as vanity percentages.",
        "competitors_winning_with": winning[:6],
        "recommended_experiments": experiments[:5],
        "top_formats": [_title(fmt) for fmt, _ in formats.most_common(4)],
        "your_primary_format": user_ig.get("primary_format"),
    }


def _build_landscape(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    competitors: list[dict[str, Any]],
    region: str | None,
) -> dict[str, Any]:
    industry = company_profile.get("industry") or company.get("industry") or "Software Services"
    market = region or company.get("region") or company_profile.get("region") or "Your market"

    user_services = " ".join(
        str(s).lower() for s in (company_profile.get("services") or company.get("services") or [])
    )
    x_axis = "AI specialization" if "ai" in user_services else "Specialization"
    y_axis = "Enterprise"

    placements = [
        {
            "name": company.get("name") or "Your Company",
            "is_you": True,
            "x": "center",
            "y": "mid",
            "note": "Your company",
        }
    ]
    for comp in sorted(competitors, key=_similarity_percent, reverse=True)[:6]:
        name = _comp_name(comp)
        services = " ".join(str(s).lower() for s in _service_terms(comp))
        x = "right" if "ai" in services or "automation" in services else "left"
        y = "high" if "enterprise" in services or _similarity_percent(comp) >= 80 else "mid"
        if "sme" in services or "startup" in services:
            y = "low"
        placements.append({"name": name, "is_you": False, "x": x, "y": y, "note": _why_similar(comp)})

    return {
        "question": "Where should I compete?",
        "market": market,
        "industry": industry,
        "axes": {"x": x_axis, "y": y_axis},
        "summary": (
            f"Market: {market}. Industry: {industry}. "
            f"You sit between general IT players and more specialized peers."
        ),
        "placements": placements,
    }


def _build_next_actions(
    *,
    strengths: dict[str, Any],
    opportunities: dict[str, Any],
    content: dict[str, Any],
    position: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []

    for gap in (opportunities.get("gaps") or [])[:3]:
        if gap.get("opportunity") != "High":
            continue
        area = gap.get("area")
        actions.append(
            {
                "priority": "high",
                "title": f"Build {area} positioning",
                "evidence": f"{gap.get('promoted_by')}. You: {gap.get('you')}.",
                "action": (
                    f"Add {area} to your service positioning if you genuinely offer it, "
                    "with a dedicated page or case study."
                ),
            }
        )

    if any(s.get("area") == "Thought Leadership" for s in (strengths.get("strengths") or [])):
        actions.append(
            {
                "priority": "medium",
                "title": "Increase thought-leadership content",
                "evidence": "Multiple competitors lean on LinkedIn thought leadership.",
                "action": "Publish 2 thought-leadership posts per week (founder POV + industry insight).",
            }
        )

    themes = content.get("competitors_winning_with") or []
    if themes:
        actions.append(
            {
                "priority": "medium",
                "title": "Run content experiments on winning themes",
                "evidence": f"Competitors win with: {', '.join(themes[:4])}.",
                "action": f"Test: {', '.join((content.get('recommended_experiments') or [])[:3])}.",
            }
        )

    user_ig = ((company_analysis or {}).get("user_instagram") or {}).get("instagram") or {}
    user_eng = float(user_ig.get("avg_engagement_rate") or 0)
    market_engs = [
        float(
            (c.get("instagram_analysis") or {}).get("avg_engagement_rate")
            or (c.get("content_strategy") or {}).get("avg_engagement_rate")
            or 0
        )
        for c in competitors
    ]
    market_engs = [e for e in market_engs if e > 0]
    market_avg = round(sum(market_engs) / max(len(market_engs), 1), 1) if market_engs else 0
    if market_avg and user_eng and market_avg > user_eng + 0.5:
        actions.append(
            {
                "priority": "low",
                "title": "Improve Instagram presence",
                "evidence": f"Competitor engagement is {market_avg}% vs your {user_eng}%.",
                "action": "Test short-form educational content for 4 weeks and compare engagement.",
            }
        )

    if position.get("differentiation_opportunity") and len(actions) < 4:
        actions.append(
            {
                "priority": "high",
                "title": "Clarify differentiation",
                "evidence": f"Market similarity score: {position.get('similarity_to_market')}%.",
                "action": position.get("differentiation_opportunity"),
            }
        )

    if not actions and competitors:
        actions.append(
            {
                "priority": "medium",
                "title": "Validate competitor service claims",
                "evidence": f"{len(competitors)} competitors analyzed.",
                "action": "Review top 3 competitor websites and capture services you can truthfully match or counter.",
            }
        )

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda item: priority_rank.get(str(item.get("priority")), 9))
    return {
        "question": "What should I do next?",
        "summary": "Actions derived from competitor evidence — not generic advice.",
        "actions": actions[:6],
    }


def build_customer_insights(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any] | None = None,
    company_analysis: dict[str, Any] | None = None,
    competitors: list[dict[str, Any]] | None = None,
    competitor_intelligence_report: dict[str, Any] | None = None,
    gap_analysis: dict[str, Any] | None = None,
    content_mix: list[dict[str, Any]] | None = None,
    market_position: dict[str, Any] | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Assemble the 7-question customer brief from existing analysis artifacts."""
    profile = company_profile or {}
    comps = competitors or []
    intel = competitor_intelligence_report or {}
    gaps = gap_analysis or {}
    mix = content_mix or []

    real_competitors = _build_real_competitors(comps)
    strengths = _build_competitive_strengths(
        company=company,
        company_profile=profile,
        competitors=comps,
        gap_analysis=gaps,
        intel_report=intel,
    )
    opportunities = _build_opportunity_gaps(
        company=company,
        company_profile=profile,
        competitors=comps,
        gap_analysis=gaps,
        intel_report=intel,
    )
    positioning = _build_market_positioning(
        company=company,
        company_profile=profile,
        competitors=comps,
        intel_report=intel,
        market_position=market_position,
    )
    content = _build_content_opportunity(
        company_analysis=company_analysis,
        competitors=comps,
        content_mix=mix,
        gap_analysis=gaps,
    )
    landscape = _build_landscape(
        company=company,
        company_profile=profile,
        competitors=comps,
        region=region,
    )
    next_actions = _build_next_actions(
        strengths=strengths,
        opportunities=opportunities,
        content=content,
        position=positioning,
        company_analysis=company_analysis,
        competitors=comps,
    )

    return {
        "version": 1,
        "principles": [
            "Who are my real competitors?",
            "What are competitors doing better than me?",
            "Where are my opportunities?",
            "How should I position myself?",
            "What content should I create?",
            "Where should I compete?",
            "What should I do next?",
        ],
        "real_competitors": real_competitors,
        "competitive_strengths": strengths,
        "opportunity_gaps": opportunities,
        "market_positioning": positioning,
        "content_opportunity": content,
        "competitive_landscape": landscape,
        "next_actions": next_actions,
    }


__all__ = [
    "build_customer_insights",
    "clean_gap_terms",
    "is_meaningful_gap_term",
]
