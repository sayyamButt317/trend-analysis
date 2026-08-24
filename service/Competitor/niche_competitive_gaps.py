from __future__ import annotations
import re
from collections import Counter
from typing import Any
from service.Competitor.competitor_intelligence_report import (
    _service_terms,
    _technology_terms,
)
from service.Competitor.gap_filters import clean_gap_terms, is_meaningful_gap_term
from service.Competitor.signal_extractor import (
    collect_text_blobs,
    extract_industries_targeted,
)


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _title_label(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _priority_from_count(count: int, total: int) -> str:
    if total <= 0:
        return "low"
    pct = count / total * 100
    if pct >= 66 or count >= 3:
        return "high"
    if pct >= 33 or count >= 2:
        return "medium"
    return "low"


def _user_has_term(term: str, owned: set[str]) -> bool:
    needle = _normalize(term)
    if not needle:
        return False
    for item in owned:
        if needle == item or needle in item or item in needle:
            return True
    return False


def _build_niche_vocabulary(
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
) -> set[str]:
    profile = company_profile or {}
    analysis = company_analysis or {}
    dna = analysis.get("company_dna") or {}
    vocab: set[str] = set()

    def _add_values(values: Any) -> None:
        if isinstance(values, str):
            values = [values]
        for item in values or []:
            text = _normalize(item)
            if len(text) > 2:
                vocab.add(text)
            for token in re.split(r"[^a-z0-9+/#]+", text):
                if len(token) > 2:
                    vocab.add(token)

    _add_values(profile.get("services"))
    _add_values(profile.get("flagship_services"))
    _add_values(profile.get("technologies"))
    _add_values(profile.get("keywords"))
    _add_values(profile.get("target_audience"))
    _add_values(profile.get("industry"))
    _add_values(profile.get("niche"))
    _add_values(profile.get("industries"))
    _add_values(dna.get("services"))
    _add_values(dna.get("keywords"))
    _add_values(dna.get("technologies"))

    detected = (
        analysis.get("detected_niche")
        or ((analysis.get("user_instagram") or {}).get("detected_niche"))
        or ((analysis.get("instagram") or {}).get("detected_niche"))
    )
    _add_values(detected)

    positioning = _normalize(profile.get("positioning") or profile.get("value_proposition"))
    for token in re.split(r"[^a-z0-9+/#]+", positioning):
        if len(token) > 3:
            vocab.add(token)

    return vocab


def _matches_niche(term: str, niche_vocab: set[str], user_owned: set[str]) -> bool:
    label = _normalize(term)
    if not label:
        return False
    if not niche_vocab:
        return True
    if _user_has_term(label, user_owned):
        return True
    words = set(re.split(r"[^a-z0-9+/#]+", label))
    for token in niche_vocab:
        if len(token) < 2:
            continue
        if token in label or label in token or token in words:
            return True
    for word in words:
        if len(word) >= 2 and word in niche_vocab:
            return True
    return False


def _is_market_standard(count: int, total: int) -> bool:
    if total <= 0:
        return False
    return count >= max(2, (total + 1) // 2)


def _collect_service_counts(competitors: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for comp in competitors:
        seen: set[str] = set()
        for svc in _service_terms(comp):
            key = _normalize(svc)
            if key and key not in seen:
                seen.add(key)
                counts[key] += 1
    return counts


def _collect_technology_counts(competitors: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for comp in competitors:
        seen: set[str] = set()
        for tech in _technology_terms(comp):
            key = _normalize(tech)
            if key and key not in seen:
                seen.add(key)
                counts[key] += 1
    return counts


def _user_service_set(company_profile: dict[str, Any], company_analysis: dict[str, Any] | None) -> set[str]:
    profile = company_profile or {}
    dna = (company_analysis or {}).get("company_dna") or {}
    owned: set[str] = set()
    for svc in list(profile.get("services") or []) + list(dna.get("services") or []):
        owned.add(_normalize(svc))
    return {item for item in owned if item}


def _user_technology_set(company_profile: dict[str, Any], company_analysis: dict[str, Any] | None) -> set[str]:
    profile = company_profile or {}
    dna = (company_analysis or {}).get("company_dna") or {}
    owned: set[str] = set()
    for tech in list(profile.get("technologies") or []) + list(dna.get("technologies") or []):
        owned.add(_normalize(tech))
    return {item for item in owned if item}


def _build_service_gaps(
    *,
    competitors: list[dict[str, Any]],
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    niche_vocab: set[str],
) -> list[dict[str, Any]]:
    user_services = _user_service_set(company_profile, company_analysis)
    counts = _collect_service_counts(competitors)
    total = len(competitors)
    gaps: list[dict[str, Any]] = []

    for raw_key, count in counts.most_common():
        label = _title_label(raw_key)
        if not is_meaningful_gap_term(label):
            continue
        if not _matches_niche(label, niche_vocab, user_services) and not _is_market_standard(count, total):
            continue
        user_has = _user_has_term(label, user_services)
        if user_has:
            continue
        gaps.append(
            {
                "service": label,
                "competitors_using": count,
                "user_has": False,
                "priority": _priority_from_count(count, total),
            }
        )
    return gaps[:12]


def _build_technology_gaps(
    *,
    competitors: list[dict[str, Any]],
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    niche_vocab: set[str],
) -> list[dict[str, Any]]:
    user_tech = _user_technology_set(company_profile, company_analysis)
    counts = _collect_technology_counts(competitors)
    total = len(competitors)
    gaps: list[dict[str, Any]] = []

    for raw_key, count in counts.most_common():
        label = _title_label(raw_key)
        if not is_meaningful_gap_term(label):
            continue
        if not _matches_niche(label, niche_vocab, user_tech) and not _is_market_standard(count, total):
            continue
        if _user_has_term(label, user_tech):
            continue
        gaps.append(
            {
                "technology": label,
                "competitors_using": count,
                "user_has": False,
                "priority": _priority_from_count(count, total),
            }
        )
    return gaps[:10]


def _competitor_has_clear_positioning(comp: dict[str, Any]) -> bool:
    intel = comp.get("website_intelligence") or {}
    li = comp.get("linkedin_analysis") or {}
    positioning = _normalize(intel.get("positioning") or comp.get("positioning") or li.get("tagline"))
    industries = extract_industries_targeted(collect_text_blobs(comp))
    return bool(
        len(positioning) >= 24
        or industries
        or li.get("industry")
        or intel.get("value_proposition")
    )


def _user_has_industry_focus(company_profile: dict[str, Any]) -> bool:
    profile = company_profile or {}
    if profile.get("industry") or profile.get("niche"):
        return True
    audience = profile.get("target_audience") or profile.get("industries_targeted") or []
    return len(audience) >= 1


def _build_positioning_gaps(
    *,
    competitors: list[dict[str, Any]],
    company_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    total = len(competitors)
    if total == 0:
        return []

    clear_positioning = sum(1 for comp in competitors if _competitor_has_clear_positioning(comp))
    gaps: list[dict[str, Any]] = []

    if clear_positioning >= max(2, total // 3) and not _user_has_industry_focus(company_profile):
        gaps.append(
            {
                "gap": "Industry specialization",
                "competitors_with_clear_positioning": clear_positioning,
                "priority": _priority_from_count(clear_positioning, total),
            }
        )

    industry_counts: Counter[str] = Counter()
    user_industries = {
        _normalize(item)
        for item in (
            list(company_profile.get("target_audience") or [])
            + list(company_profile.get("industries_targeted") or [])
            + ([company_profile.get("industry")] if company_profile.get("industry") else [])
        )
        if item
    }

    for comp in competitors:
        for industry in extract_industries_targeted(collect_text_blobs(comp)):
            key = _normalize(industry)
            if key:
                industry_counts[key] += 1

    for industry, count in industry_counts.most_common(6):
        if count < max(2, total // 4):
            continue
        if industry in user_industries:
            continue
        label = _title_label(industry)
        gaps.append(
            {
                "gap": f"{label} vertical positioning",
                "competitors_with_clear_positioning": count,
                "priority": _priority_from_count(count, total),
            }
        )

    user_positioning = _normalize(
        company_profile.get("positioning") or company_profile.get("value_proposition")
    )
    enterprise_hits = sum(
        1
        for comp in competitors
        if "enterprise" in collect_text_blobs(comp).lower()
        or "b2b" in collect_text_blobs(comp).lower()
    )
    if enterprise_hits >= max(2, total // 3) and "enterprise" not in user_positioning:
        gaps.append(
            {
                "gap": "Enterprise / B2B positioning",
                "competitors_with_clear_positioning": enterprise_hits,
                "priority": _priority_from_count(enterprise_hits, total),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in gaps:
        key = row["gap"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:8]


def _coverage_label(post_count: int) -> str:
    if post_count >= 4:
        return "high"
    if post_count >= 2:
        return "medium"
    return "low"


def _build_content_gaps(
    *,
    competitors: list[dict[str, Any]],
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    processed_posts: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    content_mix: list[dict[str, Any]],
    niche_vocab: set[str],
) -> list[dict[str, Any]]:
    user_handle = _normalize(
        company_profile.get("instagram_username")
        or ((company_analysis or {}).get("user_instagram") or {}).get("username")
    ).lstrip("@")

    user_topic_counts: Counter[str] = Counter()
    competitor_topic_counts: Counter[str] = Counter()
    competitor_theme_counts: Counter[str] = Counter()

    for post in processed_posts or []:
        username = _normalize(post.get("username")).lstrip("@")
        topic = _title_label(post.get("topic") or "General")
        if username == user_handle and user_handle:
            user_topic_counts[topic] += 1
        elif username:
            competitor_topic_counts[topic] += 1

    for row in topics or []:
        topic = _title_label(row.get("topic") or "General")
        if topic.lower() == "general":
            continue
        creator_count = int(row.get("creator_count") or 0)
        if creator_count:
            competitor_topic_counts[topic] = max(competitor_topic_counts[topic], creator_count)

    for comp in competitors:
        strategy = comp.get("content_strategy") or {}
        ig = comp.get("instagram_analysis") or {}
        for theme in strategy.get("themes") or ig.get("content_themes") or []:
            label = _title_label(theme.get("theme") if isinstance(theme, dict) else theme)
            if label and label.lower() != "general":
                competitor_theme_counts[label] += 1
        for category in strategy.get("content_categories") or ig.get("content_categories") or []:
            label = _title_label(category.get("category") if isinstance(category, dict) else category)
            if label and label.lower() != "general":
                competitor_theme_counts[label] += 1

    for profile in content_mix or []:
        username = _normalize(profile.get("username")).lstrip("@")
        if username == user_handle:
            continue
        for theme in profile.get("content_themes") or []:
            label = _title_label(theme.get("theme") if isinstance(theme, dict) else theme)
            if label:
                competitor_theme_counts[label] += 1

    merged: Counter[str] = Counter()
    merged.update(competitor_topic_counts)
    merged.update(competitor_theme_counts)

    total = len(competitors)
    gaps: list[dict[str, Any]] = []
    for topic, count in merged.most_common(15):
        if count < max(1, total // 5):
            continue
        if not _matches_niche(topic, niche_vocab, set()) and count < max(2, total // 3):
            continue
        user_posts = user_topic_counts.get(topic, 0)
        coverage = _coverage_label(user_posts)
        if coverage == "high":
            continue
        gaps.append(
            {
                "topic": topic,
                "competitors_covering": count,
                "user_coverage": coverage,
            }
        )

    return gaps[:10]


def build_niche_competitive_gaps(
    *,
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
    processed_posts: list[dict[str, Any]] | None = None,
    topics: list[dict[str, Any]] | None = None,
    content_mix: list[dict[str, Any]] | None = None,
    gap_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build niche-filtered competitive gaps for the user company."""
    profile = company_profile or {}
    niche_vocab = _build_niche_vocabulary(profile, company_analysis)
    niche_label = (
        profile.get("niche")
        or profile.get("industry")
        or (company_analysis or {}).get("detected_niche")
        or "company niche"
    )

    service_gaps = _build_service_gaps(
        competitors=competitors,
        company_profile=profile,
        company_analysis=company_analysis,
        niche_vocab=niche_vocab,
    )
    technology_gaps = _build_technology_gaps(
        competitors=competitors,
        company_profile=profile,
        company_analysis=company_analysis,
        niche_vocab=niche_vocab,
    )
    positioning_gaps = _build_positioning_gaps(
        competitors=competitors,
        company_profile=profile,
    )
    content_gaps = _build_content_gaps(
        competitors=competitors,
        company_profile=profile,
        company_analysis=company_analysis,
        processed_posts=processed_posts or [],
        topics=topics or [],
        content_mix=content_mix or [],
        niche_vocab=niche_vocab,
    )

    # Enrich from prior gap_analysis when niche filter is thin.
    if len(service_gaps) < 3 and gap_analysis:
        existing = {g["service"].lower() for g in service_gaps}
        total = max(len(competitors), 1)
        for svc in clean_gap_terms(gap_analysis.get("service_gaps") or [], limit=8):
            if svc.lower() in existing:
                continue
            if not _matches_niche(svc, niche_vocab, _user_service_set(profile, company_analysis)):
                continue
            service_gaps.append(
                {
                    "service": svc,
                    "competitors_using": max(1, total // 2),
                    "user_has": False,
                    "priority": "medium",
                }
            )

    return {
        "service_gaps": service_gaps,
        "positioning_gaps": positioning_gaps,
        "content_gaps": content_gaps,
        "technology_gaps": technology_gaps,
    }
