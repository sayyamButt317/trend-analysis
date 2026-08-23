"""Build competitor-vs-company comparisons and quantified competitive gaps."""

from __future__ import annotations

from typing import Any

from service.Competitor.competitor_intelligence_report import (
    _competitor_lookup_key,
    _service_terms,
    _technology_terms,
    similarity_to_percentages,
)
from service.Competitor.gap_filters import clean_gap_terms, is_meaningful_gap_term


def _normalize_terms(values: Any) -> set[str]:
    if not values:
        return set()
    if isinstance(values, str):
        values = [values]
    out: set[str] = set()
    for item in values:
        text = str(item or "").strip().lower()
        if text and len(text) > 1:
            out.add(text)
    return out


def _list_comparison(company_terms: list[str], competitor_terms: list[str]) -> dict[str, Any]:
    company = _normalize_terms(company_terms)
    competitor = _normalize_terms(competitor_terms)
    universe = company | competitor
    shared = sorted(company & competitor)
    company_only = sorted(company - competitor)
    competitor_only = sorted(competitor - company)
    overlap_pct = round(len(shared) / max(len(universe), 1) * 100, 1)
    return {
        "shared": shared[:12],
        "company_only": company_only[:12],
        "competitor_only": competitor_only[:12],
        "shared_count": len(shared),
        "company_only_count": len(company_only),
        "competitor_only_count": len(competitor_only),
        "overlap_pct": overlap_pct,
    }


def _user_social_metrics(company_analysis: dict[str, Any] | None) -> dict[str, Any]:
    analysis = company_analysis or {}
    ig_block = (analysis.get("user_instagram") or {}).get("instagram") or analysis.get("instagram") or {}
    strategy = ig_block if isinstance(ig_block, dict) else {}
    return {
        "followers": strategy.get("followers"),
        "avg_engagement_rate": strategy.get("avg_engagement_rate"),
        "primary_format": strategy.get("primary_format"),
        "posting_frequency": strategy.get("posting_frequency"),
        "content_themes": [
            (t.get("theme") if isinstance(t, dict) else str(t))
            for t in (strategy.get("content_themes") or [])[:6]
        ],
    }


def _competitor_social_metrics(competitor: dict[str, Any]) -> dict[str, Any]:
    ig = competitor.get("instagram_analysis") or {}
    strategy = competitor.get("content_strategy") or {}
    return {
        "followers": competitor.get("followers"),
        "avg_engagement_rate": strategy.get("avg_engagement_rate") or ig.get("avg_engagement_rate"),
        "primary_format": strategy.get("primary_format") or ig.get("primary_format"),
        "posting_frequency": ig.get("posting_frequency"),
        "content_themes": [
            (t.get("theme") if isinstance(t, dict) else str(t))
            for t in (strategy.get("themes") or ig.get("content_themes") or [])[:6]
        ],
    }


def _social_delta(company: dict[str, Any], competitor: dict[str, Any]) -> dict[str, Any]:
    c_followers = float(company.get("followers") or 0)
    comp_followers = float(competitor.get("followers") or 0)
    c_eng = float(company.get("avg_engagement_rate") or 0)
    comp_eng = float(competitor.get("avg_engagement_rate") or 0)
    follower_gap = round(comp_followers - c_followers, 1) if (c_followers or comp_followers) else None
    engagement_gap = round(comp_eng - c_eng, 2) if (c_eng or comp_eng) else None
    return {
        "follower_gap": follower_gap,
        "engagement_gap_pct": engagement_gap,
        "company_ahead_on_engagement": bool(c_eng and comp_eng and c_eng > comp_eng),
        "competitor_ahead_on_engagement": bool(c_eng and comp_eng and comp_eng > c_eng),
        "company_ahead_on_followers": bool(c_followers and comp_followers and c_followers > comp_followers),
        "competitor_ahead_on_followers": bool(c_followers and comp_followers and comp_followers > c_followers),
    }


def _dimension_verdict(company_pct: int, competitor_overlap_pct: int) -> str:
    """How closely the competitor overlaps company DNA on a dimension."""
    if competitor_overlap_pct >= 75:
        return "direct_rival"
    if competitor_overlap_pct >= 50:
        return "strong_overlap"
    if competitor_overlap_pct >= 25:
        return "partial_overlap"
    return "low_overlap"


def _overall_position(
    *,
    similarity_pct: int,
    service_overlap: float,
    social_delta: dict[str, Any],
) -> dict[str, Any]:
    ahead_signals = sum(
        1
        for flag in (
            social_delta.get("company_ahead_on_engagement"),
            social_delta.get("company_ahead_on_followers"),
        )
        if flag
    )
    behind_signals = sum(
        1
        for flag in (
            social_delta.get("competitor_ahead_on_engagement"),
            social_delta.get("competitor_ahead_on_followers"),
        )
        if flag
    )
    if similarity_pct >= 70 and behind_signals >= ahead_signals:
        position = "direct_rival"
    elif behind_signals > ahead_signals:
        position = "behind"
    elif ahead_signals > behind_signals:
        position = "ahead"
    else:
        position = "parity"

    summary_parts: list[str] = []
    if similarity_pct:
        summary_parts.append(f"{similarity_pct}% overall DNA overlap")
    if service_overlap:
        summary_parts.append(f"{service_overlap:.0f}% service overlap")
    if behind_signals:
        summary_parts.append("competitor leads on visible social metrics")
    elif ahead_signals:
        summary_parts.append("you lead on visible social metrics")

    return {
        "position": position,
        "similarity_pct": similarity_pct,
        "summary": "; ".join(summary_parts) if summary_parts else "Limited overlap signals available.",
    }


def _company_snapshot(
    company: dict[str, Any],
    company_profile: dict[str, Any] | None,
    company_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    profile = company_profile or {}
    dna = (company_analysis or {}).get("company_dna") or {}
    return {
        "name": company.get("name") or profile.get("name"),
        "website": company.get("website") or profile.get("website"),
        "industry": profile.get("industry") or company.get("industry"),
        "services": list(profile.get("services") or company.get("services") or dna.get("services") or [])[:15],
        "technologies": list(profile.get("technologies") or company.get("technologies") or dna.get("technologies") or [])[:15],
        "target_audience": list(profile.get("target_audience") or dna.get("target_audience") or [])[:10],
        "keywords": list(profile.get("keywords") or company.get("keywords") or dna.get("keywords") or [])[:12],
        "social": _user_social_metrics(company_analysis),
    }


def _competitor_snapshot(competitor: dict[str, Any]) -> dict[str, Any]:
    intel = competitor.get("website_intelligence") or {}
    return {
        "name": competitor.get("name"),
        "username": competitor.get("username"),
        "website": competitor.get("website"),
        "linkedin_url": competitor.get("linkedin_url"),
        "services": clean_gap_terms(
            [
                *(competitor.get("website_services") or []),
                *(intel.get("services") or []),
                *_service_terms(competitor),
            ],
            limit=15,
        ),
        "technologies": clean_gap_terms(_technology_terms(competitor), limit=15),
        "social": _competitor_social_metrics(competitor),
        "is_hiring": competitor.get("is_hiring"),
        "company_size": competitor.get("linkedin_company_size") or competitor.get("company_size"),
        "linkedin_total_employees": competitor.get("linkedin_total_employees"),
        "linkedin_company_size": competitor.get("linkedin_company_size") or competitor.get("company_size"),
        "linkedin_employee_range": competitor.get("linkedin_employee_range"),
        "linkedin_profiles_sampled": competitor.get("linkedin_profiles_sampled")
        or len(competitor.get("employees") or []),
    }


def build_competitor_vs_company_comparison(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any] | None,
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
    competitor_intelligence_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Side-by-side company vs each competitor with quantified overlap."""
    intel = competitor_intelligence_report or {}
    company_snap = _company_snapshot(company, company_profile, company_analysis)
    company_services = company_snap["services"]
    company_tech = company_snap["technologies"]
    company_social = company_snap["social"]

    score_lookup = {
        _competitor_lookup_key(item): item
        for item in intel.get("similarity_vs_competitors") or []
        if _competitor_lookup_key(item)
    }

    comparisons: list[dict[str, Any]] = []
    for comp in competitors:
        matched = score_lookup.get(_competitor_lookup_key(comp)) or comp
        similarity = matched.get("similarity") or comp.get("similarity") or {}
        sim_pct = matched.get("similarity_percentages") or similarity_to_percentages(similarity)
        comp_snap = _competitor_snapshot(comp)

        services_cmp = _list_comparison(company_services, comp_snap["services"])
        tech_cmp = _list_comparison(company_tech, comp_snap["technologies"])
        social_delta = _social_delta(company_social, comp_snap["social"])

        company_themes = _normalize_terms(company_social.get("content_themes"))
        comp_themes = _normalize_terms(comp_snap["social"].get("content_themes"))
        theme_shared = sorted(company_themes & comp_themes)
        theme_comp_only = sorted(comp_themes - company_themes)

        dimensions = {
            "services": {
                "overlap_pct": services_cmp["overlap_pct"],
                "similarity_pct": sim_pct.get("services"),
                "verdict": _dimension_verdict(sim_pct.get("services") or 0, services_cmp["overlap_pct"]),
            },
            "technology": {
                "overlap_pct": tech_cmp["overlap_pct"],
                "similarity_pct": sim_pct.get("tech") or sim_pct.get("technology"),
                "verdict": _dimension_verdict(sim_pct.get("tech") or 0, tech_cmp["overlap_pct"]),
            },
            "marketing": {
                "similarity_pct": sim_pct.get("marketing"),
                "verdict": _dimension_verdict(sim_pct.get("marketing") or 0, sim_pct.get("marketing") or 0),
            },
            "content": {
                "similarity_pct": sim_pct.get("content"),
                "shared_themes": theme_shared[:6],
                "competitor_only_themes": theme_comp_only[:6],
                "verdict": _dimension_verdict(sim_pct.get("content") or 0, len(theme_shared) * 20),
            },
            "location": {
                "similarity_pct": sim_pct.get("location"),
                "verdict": _dimension_verdict(sim_pct.get("location") or 0, sim_pct.get("location") or 0),
            },
        }

        comparisons.append(
            {
                "competitor": comp_snap,
                "overall_similarity_pct": sim_pct.get("overall"),
                "match_score": matched.get("match_score") or similarity.get("overall"),
                "similarity_dimensions": dimensions,
                "services_comparison": services_cmp,
                "technology_comparison": tech_cmp,
                "social_comparison": {
                    "company": company_social,
                    "competitor": comp_snap["social"],
                    "delta": social_delta,
                },
                "content_comparison": {
                    "company_primary_format": company_social.get("primary_format"),
                    "competitor_primary_format": comp_snap["social"].get("primary_format"),
                    "shared_themes": theme_shared,
                    "competitor_only_themes": theme_comp_only,
                },
                "hiring_comparison": {
                    "company_is_hiring": (company_analysis or {}).get("is_hiring"),
                    "competitor_is_hiring": comp.get("is_hiring"),
                },
                "competitive_position": _overall_position(
                    similarity_pct=int(sim_pct.get("overall") or 0),
                    service_overlap=float(services_cmp.get("overlap_pct") or 0),
                    social_delta=social_delta,
                ),
            }
        )

    comparisons.sort(
        key=lambda item: float(item.get("overall_similarity_pct") or item.get("match_score") or 0),
        reverse=True,
    )

    return {
        "company": company_snap,
        "competitor_count": len(comparisons),
        "comparisons": comparisons,
        "summary": (
            f"Compared {company_snap.get('name') or 'your company'} against {len(comparisons)} competitors "
            f"with side-by-side service, technology, social, and content overlap."
        ),
    }


def _gap_priority(market_coverage_pct: float) -> str:
    if market_coverage_pct >= 66:
        return "high"
    if market_coverage_pct >= 33:
        return "medium"
    return "low"


def _gap_entry(
    *,
    category: str,
    item: str,
    competitor_count: int,
    total_competitors: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage = round(competitor_count / max(total_competitors, 1) * 100, 1)
    entry = {
        "category": category,
        "item": item,
        "competitor_count": competitor_count,
        "market_coverage_pct": coverage,
        "gap_score": coverage,
        "priority": _gap_priority(coverage),
    }
    if extra:
        entry.update(extra)
    return entry


def build_quantified_competitive_gaps(
    *,
    gap_analysis: dict[str, Any] | None,
    competitor_intelligence_report: dict[str, Any] | None,
    competitor_count: int = 0,
) -> dict[str, Any]:
    """Aggregate competitive gaps with counts, coverage %, and priority scores."""
    gaps_raw = gap_analysis or {}
    intel = competitor_intelligence_report or {}
    intel_gaps = intel.get("gaps") or {}
    total = int(competitor_count or gaps_raw.get("competitor_count") or intel.get("competitor_count") or 0)

    unified: list[dict[str, Any]] = []

    def _add_from_strings(category: str, values: list[Any], *, count_key: str = "competitor_count") -> None:
        for raw in values or []:
            if isinstance(raw, dict):
                item = raw.get("item") or raw.get("signal") or raw.get("content_type") or raw.get("platform") or raw.get("industry")
                count = int(raw.get(count_key) or raw.get("count") or 1)
            else:
                item = str(raw)
                count = 1
            if not is_meaningful_gap_term(item):
                continue
            unified.append(
                _gap_entry(
                    category=category,
                    item=str(item),
                    competitor_count=min(count, total) if total else count,
                    total_competitors=max(total, 1),
                )
            )

    _add_from_strings("service", intel_gaps.get("services") or gaps_raw.get("service_gaps") or [])
    _add_from_strings("technology", intel_gaps.get("technologies") or gaps_raw.get("technology_gaps") or [])
    _add_from_strings("keyword", gaps_raw.get("keyword_gaps") or [])
    _add_from_strings("business_signal", intel_gaps.get("business_signals") or [])
    _add_from_strings("content", intel_gaps.get("content_types") or [])
    _add_from_strings("industry", intel_gaps.get("industries_targeted") or [])
    _add_from_strings("review_platform", intel_gaps.get("review_platforms") or [])

    for theme in gaps_raw.get("dominant_competitor_themes") or []:
        label = theme.get("theme") if isinstance(theme, dict) else theme
        count = int(theme.get("count") or 1) if isinstance(theme, dict) else 1
        if is_meaningful_gap_term(label):
            unified.append(
                _gap_entry(
                    category="content_theme",
                    item=str(label),
                    competitor_count=min(count, total) if total else count,
                    total_competitors=max(total, 1),
                )
            )

    for fmt in gaps_raw.get("dominant_competitor_formats") or []:
        label = fmt.get("format") if isinstance(fmt, dict) else fmt
        count = int(fmt.get("count") or 1) if isinstance(fmt, dict) else 1
        if is_meaningful_gap_term(label):
            unified.append(
                _gap_entry(
                    category="content_format",
                    item=str(label),
                    competitor_count=min(count, total) if total else count,
                    total_competitors=max(total, 1),
                )
            )

    # Deduplicate by category+item keeping highest gap_score
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in unified:
        key = (row["category"], row["item"].lower())
        if key not in deduped or row["gap_score"] > deduped[key]["gap_score"]:
            deduped[key] = row
    ranked = sorted(deduped.values(), key=lambda r: (r["gap_score"], r["competitor_count"]), reverse=True)

    categories: dict[str, Any] = {}
    for row in ranked:
        bucket = categories.setdefault(
            row["category"],
            {"gap_count": 0, "avg_gap_score": 0.0, "top_gaps": []},
        )
        bucket["gap_count"] += 1
        bucket["top_gaps"].append(row)
    for bucket in categories.values():
        scores = [float(item["gap_score"]) for item in bucket["top_gaps"]]
        bucket["avg_gap_score"] = round(sum(scores) / max(len(scores), 1), 1)
        bucket["top_gaps"] = bucket["top_gaps"][:8]

    high_priority = sum(1 for row in ranked if row["priority"] == "high")

    return {
        "competitor_count": total,
        "total_gaps": len(ranked),
        "high_priority_gaps": high_priority,
        "categories": categories,
        "gaps": ranked[:30],
        "summary": (
            f"Identified {len(ranked)} quantified competitive gaps across {total or 'analyzed'} competitors "
            f"({high_priority} high-priority). "
            f"{gaps_raw.get('summary') or intel_gaps.get('summary') or ''}".strip()
        ),
    }


def _title_label(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _threat_level(
    *,
    overall_similarity_pct: int,
    they_stronger_count: int,
    competitive_position: str,
) -> str:
    if overall_similarity_pct >= 70 and (they_stronger_count >= 3 or competitive_position in {"direct_rival", "behind"}):
        return "High"
    if overall_similarity_pct >= 50 or they_stronger_count >= 2 or competitive_position == "behind":
        return "Medium"
    if overall_similarity_pct >= 35:
        return "Low"
    return "Minimal"


def _why_competitor_label(
    *,
    comparison: dict[str, Any],
    raw: dict[str, Any],
) -> str:
    reasons = list(raw.get("match_reasons") or [])
    if raw.get("why_competitor"):
        return str(raw["why_competitor"]).strip()
    if raw.get("description"):
        return str(raw["description"]).strip()
    if reasons:
        return str(reasons[0]).strip()

    position = (comparison.get("competitive_position") or {}).get("summary")
    if position:
        return str(position).strip()

    sim = int(comparison.get("overall_similarity_pct") or 0)
    name = (comparison.get("competitor") or {}).get("name") or "This competitor"
    services = (comparison.get("services_comparison") or {}).get("shared") or []
    if services:
        return f"{name} overlaps {sim}% on DNA and shares services like {', '.join(services[:3])}."
    return f"{name} is a {sim}% market match in your niche."


def _strengths_from_comparison(comparison: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (they_are_stronger_at, you_are_stronger_at) labels."""
    they: list[str] = []
    you: list[str] = []

    services = comparison.get("services_comparison") or {}
    for item in services.get("competitor_only") or []:
        they.append(f"{_title_label(item)} services")
    for item in services.get("company_only") or []:
        you.append(f"{_title_label(item)} services")
    for item in services.get("shared") or []:
        if item and f"Shared: {_title_label(item)}" not in they and f"Shared: {_title_label(item)}" not in you:
            pass  # shared doesn't go to either side

    tech = comparison.get("technology_comparison") or {}
    for item in tech.get("competitor_only") or []:
        they.append(f"{_title_label(item)} technology")
    for item in tech.get("company_only") or []:
        you.append(f"{_title_label(item)} technology")

    social = (comparison.get("social_comparison") or {}).get("delta") or {}
    if social.get("competitor_ahead_on_engagement"):
        they.append("Instagram engagement rate")
    elif social.get("company_ahead_on_engagement"):
        you.append("Instagram engagement rate")
    if social.get("competitor_ahead_on_followers"):
        they.append("Instagram audience reach")
    elif social.get("company_ahead_on_followers"):
        you.append("Instagram audience reach")

    content = comparison.get("content_comparison") or {}
    comp_format = content.get("competitor_primary_format")
    user_format = content.get("company_primary_format")
    if comp_format and user_format and str(comp_format).lower() != str(user_format).lower():
        they.append(f"{comp_format} content format")
    for theme in content.get("competitor_only_themes") or []:
        they.append(f"{_title_label(theme)} content")

    hiring = comparison.get("hiring_comparison") or {}
    if hiring.get("competitor_is_hiring") and not hiring.get("company_is_hiring"):
        they.append("Active hiring signals")
    elif hiring.get("company_is_hiring") and not hiring.get("competitor_is_hiring"):
        you.append("Active hiring signals")

    comp_snap = comparison.get("competitor") or {}
    if comp_snap.get("is_hiring") and "Active hiring signals" not in they:
        if not hiring.get("company_is_hiring"):
            they.append("Active hiring signals")

    dimensions = comparison.get("similarity_dimensions") or {}
    for dim_key, label in (
        ("marketing", "Marketing positioning"),
        ("content", "Content strategy"),
        ("location", "Regional presence"),
    ):
        dim = dimensions.get(dim_key) or {}
        verdict = dim.get("verdict")
        pct = int(dim.get("similarity_pct") or dim.get("overlap_pct") or 0)
        if verdict == "direct_rival" and pct >= 70:
            they.append(label)

    they = list(dict.fromkeys(they))[:8]
    you = list(dict.fromkeys(you))[:8]
    return they, you


def build_competitive_matchup(
    *,
    competitor_vs_company: dict[str, Any] | None,
    raw_competitors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Who we compete against and how we compare — per-competitor cards with
    they_are_stronger_at, you_are_stronger_at, why_competitor, threat_level.
    """
    base = competitor_vs_company or {}
    comparisons = base.get("comparisons") or []

    raw_index: dict[str, dict[str, Any]] = {}
    for comp in raw_competitors or []:
        key = _competitor_lookup_key(comp)
        if key:
            raw_index[key] = comp

    cards: list[dict[str, Any]] = []
    for row in comparisons:
        comp_snap = row.get("competitor") or {}
        key = _competitor_lookup_key(comp_snap)
        raw = raw_index.get(key) or {}
        if not key:
            raw = next(
                (
                    item
                    for item in (raw_competitors or [])
                    if (item.get("name") or "").strip().lower() == (comp_snap.get("name") or "").strip().lower()
                ),
                {},
            )

        they, you = _strengths_from_comparison(row)
        position = (row.get("competitive_position") or {}).get("position") or "parity"
        sim_pct = int(row.get("overall_similarity_pct") or 0)

        cards.append(
            {
                "name": comp_snap.get("name"),
                "username": comp_snap.get("username"),
                "website": comp_snap.get("website"),
                "linkedin_url": comp_snap.get("linkedin_url"),
                "linkedin_total_employees": comp_snap.get("linkedin_total_employees") or raw.get("linkedin_total_employees"),
                "linkedin_company_size": comp_snap.get("linkedin_company_size")
                or raw.get("linkedin_company_size")
                or comp_snap.get("company_size"),
                "why_competitor": _why_competitor_label(comparison=row, raw=raw),
                "overall_similarity_pct": sim_pct,
                "match_score": row.get("match_score"),
                "similarity_percentages": {
                    "overall": sim_pct,
                    "services": (row.get("similarity_dimensions") or {}).get("services", {}).get("similarity_pct"),
                    "technology": (row.get("similarity_dimensions") or {}).get("technology", {}).get("similarity_pct"),
                    "marketing": (row.get("similarity_dimensions") or {}).get("marketing", {}).get("similarity_pct"),
                    "content": (row.get("similarity_dimensions") or {}).get("content", {}).get("similarity_pct"),
                },
                "they_are_stronger_at": they,
                "you_are_stronger_at": you,
                "threat_level": _threat_level(
                    overall_similarity_pct=sim_pct,
                    they_stronger_count=len(they),
                    competitive_position=position,
                ),
                "competitive_position": position,
                "competitive_position_summary": (row.get("competitive_position") or {}).get("summary"),
            }
        )

    high_threats = sum(1 for card in cards if card.get("threat_level") == "High")
    return {
        "summary": (
            f"You compete against {len(cards)} peer(s). "
            f"{high_threats} pose a high threat based on overlap and where they outperform you."
        ),
        "company": base.get("company") or {},
        "competitor_count": len(cards),
        "high_threat_count": high_threats,
        "competitors": cards,
    }

