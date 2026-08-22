from __future__ import annotations
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from agents.trend.Nodes.common import parse_timestamp
from service.Competitor.competitor_intelligence_report import _service_terms, _technology_terms
from service.Competitor.customer_insights import build_customer_insights
from service.Competitor.signal_extractor import (
    collect_text_blobs,
    extract_business_signals,
    extract_technologies_mentioned,
)

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_TOPIC_RE = re.compile(
    r"\b(ai agents?|generative ai|machine learning|mcp|cloud consulting|data engineering|"
    r"case stud(?:y|ies)|customer success|enterprise ai|thought leadership|automation|"
    r"software development|mobile app|devops|cybersecurity|fintech|healthcare tech)\b",
    re.I,
)


_ACRONYMS = {"ai", "mcp", "seo", "api", "aws", "gcp", "ui", "ux", "b2b", "saas", "iot", "ml"}


def _title_label(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return cleaned
    parts = cleaned.replace("_", " ").split()
    return " ".join(part.upper() if part.lower() in _ACRONYMS else part.capitalize() for part in parts)


def _priority_label(competitor_count: int, total_competitors: int) -> str:
    if total_competitors <= 0:
        return "Medium"
    share = competitor_count / total_competitors
    if share >= 0.5 or competitor_count >= 6:
        return "High"
    if share >= 0.25 or competitor_count >= 3:
        return "Medium"
    return "Low"


def _pct_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _competitor_name(comp: dict[str, Any]) -> str:
    return str(comp.get("name") or comp.get("username") or "Competitor").strip()


def _user_service_set(company: dict[str, Any], company_profile: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for source in (company_profile.get("services") or [], company.get("services") or []):
        for item in source:
            if item:
                terms.add(str(item).lower().strip())
    return terms


def _user_tech_set(company_profile: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for item in company_profile.get("technologies") or []:
        if item:
            terms.add(str(item).lower().strip())
    return terms


def _service_offerings_map(
    competitors: list[dict[str, Any]],
    user_services: set[str],
) -> dict[str, dict[str, Any]]:
    offerings: dict[str, dict[str, Any]] = defaultdict(lambda: {"competitors": set()})
    for comp in competitors:
        name = _competitor_name(comp)
        for term in _service_terms(comp):
            key = str(term).lower().strip()
            if not key or key in user_services:
                continue
            offerings[key]["competitors"].add(name)
    return offerings


def _technology_offerings_map(
    competitors: list[dict[str, Any]],
    user_tech: set[str],
) -> dict[str, dict[str, Any]]:
    offerings: dict[str, dict[str, Any]] = defaultdict(lambda: {"competitors": set()})
    for comp in competitors:
        name = _competitor_name(comp)
        for term in _technology_terms(comp):
            key = str(term).lower().strip()
            if not key or key in user_tech:
                continue
            offerings[key]["competitors"].add(name)
    return offerings


def _build_missing_services(
    *,
    competitors: list[dict[str, Any]],
    company: dict[str, Any],
    company_profile: dict[str, Any],
    intel_gaps: dict[str, Any],
    gap_analysis: dict[str, Any],
) -> dict[str, Any]:
    total = len(competitors)
    user_services = _user_service_set(company, company_profile)
    offerings = _service_offerings_map(competitors, user_services)

    for row in intel_gaps.get("services") or gap_analysis.get("service_gaps") or []:
        label = row.get("item") if isinstance(row, dict) else str(row)
        key = str(label or "").lower().strip()
        if key and key not in user_services:
            offerings[key]["competitors"].add("market")

    ranked = sorted(
        offerings.items(),
        key=lambda item: len(item[1]["competitors"]),
        reverse=True,
    )[:12]

    items: list[dict[str, Any]] = []
    for key, payload in ranked:
        comp_names = sorted(name for name in payload["competitors"] if name != "market")
        count = len(comp_names) or max(
            int((row.get("competitor_count") or 0) if isinstance(row, dict) else 0)
            for row in (intel_gaps.get("services") or [])
            if str((row.get("item") if isinstance(row, dict) else row) or "").lower() == key
        ) or 1
        if comp_names:
            count = len(comp_names)
        item: dict[str, Any] = {
            "service": _title_label(key),
            "competitor_count": count,
            "market_share": _pct_score((count / max(total, 1)) * 100),
            "priority": _priority_label(count, total),
        }
        if comp_names:
            item["top_competitors"] = comp_names[:3]
        items.append(item)

    return {
        "question": "What services are competitors offering that we are not?",
        "summary": (
            f"Competitors collectively promote {len(items)} service areas that are absent from your portfolio."
            if items
            else "Your service portfolio covers the main offerings promoted by competitors."
        ),
        "total_missing": len(items),
        "items": items,
    }


def _build_technology_gap(
    *,
    competitors: list[dict[str, Any]],
    company_profile: dict[str, Any],
    intel_gaps: dict[str, Any],
    gap_analysis: dict[str, Any],
) -> dict[str, Any]:
    total = len(competitors)
    user_tech = _user_tech_set(company_profile)
    offerings = _technology_offerings_map(competitors, user_tech)

    for row in intel_gaps.get("technologies") or gap_analysis.get("technology_gaps") or []:
        label = row.get("item") if isinstance(row, dict) else str(row)
        key = str(label or "").lower().strip()
        if key and key not in user_tech:
            offerings[key]["competitors"].add("market")

    ranked = sorted(
        offerings.items(),
        key=lambda item: len(item[1]["competitors"]),
        reverse=True,
    )[:10]

    items = []
    for key, payload in ranked:
        comp_names = sorted(name for name in payload["competitors"] if name != "market")
        count = len(comp_names) or 1
        items.append(
            {
                "technology": _title_label(key),
                "competitor_count": count,
                "priority": _priority_label(count, total),
            }
        )

    top_names = ", ".join(item["technology"] for item in items[:3])
    return {
        "question": "Which technologies are competitors using that you are not?",
        "summary": (
            f"Competitors frequently mention {top_names}."
            if top_names
            else "Your technology mentions align with the competitive set."
        ),
        "items": items,
    }


def _coverage_pct(user_terms: set[str], market_terms: set[str]) -> int:
    if not market_terms:
        return 0
    overlap = len(user_terms & market_terms)
    return _pct_score((overlap / len(market_terms)) * 100)


def _build_market_position(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
    intel_report: dict[str, Any],
    coverage: dict[str, int],
    content_score: int,
) -> dict[str, Any]:
    avg_similarity = float((intel_report.get("average_similarity") or {}).get("overall") or 0)
    analysis = company_analysis or {}
    user_ig = (analysis.get("user_instagram") or {}).get("instagram") or {}

    user_engagement = float(user_ig.get("avg_engagement_rate") or 0)
    comp_engagements = [
        float((comp.get("instagram_analysis") or {}).get("avg_engagement_rate")
              or (comp.get("content_strategy") or {}).get("avg_engagement_rate") or 0)
        for comp in competitors
    ]
    comp_engagements = [rate for rate in comp_engagements if rate > 0]
    market_engagement = round(sum(comp_engagements) / max(len(comp_engagements), 1), 2)

    user_followers = float(user_ig.get("followers") or 0)
    comp_followers = [float(comp.get("followers") or 0) for comp in competitors if comp.get("followers")]
    brand_visibility = 50
    if user_followers and comp_followers:
        rank = sum(1 for followers in comp_followers if followers > user_followers)
        brand_visibility = _pct_score((1 - rank / max(len(comp_followers), 1)) * 100)

    engagement_delta = round(user_engagement - market_engagement, 1)
    market_percentile = _pct_score(
        (avg_similarity * 35)
        + (coverage["service"] * 0.2)
        + (coverage["technology"] * 0.15)
        + (content_score * 0.15)
        + (brand_visibility * 0.15)
    )

    if avg_similarity >= 0.72 and brand_visibility >= 60:
        position_label = "Market Leader"
    elif avg_similarity >= 0.55 or brand_visibility >= 45:
        position_label = "Established Player"
    elif avg_similarity >= 0.4 or content_score >= 55:
        position_label = "Emerging Challenger"
    else:
        position_label = "Niche Specialist"

    return {
        "question": "Where do you stand in the market?",
        "position_label": position_label,
        "overall_similarity": round(avg_similarity, 2),
        "market_percentile": market_percentile,
        "engagement_vs_market": engagement_delta,
        "service_coverage": coverage["service"],
        "technology_coverage": coverage["technology"],
        "content_score": content_score,
        "brand_visibility": brand_visibility,
    }


def _build_best_social_channels(
    *,
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    analysis = company_analysis or {}
    user_ig = (analysis.get("user_instagram") or {}).get("instagram") or {}
    user_li = (analysis.get("user_linkedin") or {}).get("linkedin_analysis") or {}

    user_ig_engagement = round(float(user_ig.get("avg_engagement_rate") or 0), 1)
    comp_ig_engagements: list[float] = []
    comp_ig_count = 0
    for comp in competitors:
        ig = comp.get("instagram_analysis") or {}
        strategy = comp.get("content_strategy") or {}
        if ig or comp.get("username"):
            comp_ig_count += 1
            rate = float(ig.get("avg_engagement_rate") or strategy.get("avg_engagement_rate") or 0)
            if rate:
                comp_ig_engagements.append(rate)
    ig_market_avg = round(sum(comp_ig_engagements) / max(len(comp_ig_engagements), 1), 1)
    ig_effectiveness = _pct_score((ig_market_avg * 12) + (comp_ig_count / max(len(competitors), 1) * 40))

    comp_li_count = sum(1 for comp in competitors if comp.get("linkedin_analysis") or comp.get("linkedin_url"))
    user_tl = float(user_li.get("thought_leadership_score") or 0)
    comp_tl_scores = [
        float((comp.get("linkedin_analysis") or {}).get("thought_leadership_score") or 0)
        for comp in competitors
        if comp.get("linkedin_analysis")
    ]
    comp_tl_avg = sum(comp_tl_scores) / max(len(comp_tl_scores), 1)
    li_effectiveness = _pct_score((comp_tl_avg * 50) + (comp_li_count / max(len(competitors), 1) * 50))

    channels = [
        {
            "channel": "Instagram",
            "competitors_using": comp_ig_count,
            "your_presence": bool(user_ig or (analysis.get("user_instagram") or {}).get("username")),
            "your_engagement": user_ig_engagement,
            "market_average": ig_market_avg,
            "effectiveness_score": ig_effectiveness,
        },
        {
            "channel": "LinkedIn",
            "competitors_using": comp_li_count,
            "your_presence": bool(user_li or (analysis.get("user_linkedin") or {}).get("linkedin_url")),
            "your_engagement": round(user_tl * 10, 1) if user_tl else None,
            "market_average": round(comp_tl_avg * 10, 1) if comp_tl_avg else None,
            "effectiveness_score": li_effectiveness,
        },
    ]
    channels.sort(key=lambda row: row["effectiveness_score"], reverse=True)
    winner = channels[0]["channel"] if channels else "Instagram"
    return {
        "question": "Which social channels perform best in this market?",
        "winner": winner,
        "channels": channels,
    }


def _build_content_strategy(
    *,
    processed_posts: list[dict[str, Any]],
) -> dict[str, Any]:
    format_rates: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    category_rates: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    total_posts = max(len(processed_posts), 1)

    for post in processed_posts:
        rate = float(post.get("engagement_rate") or 0)
        media_type = post.get("media_type") or post.get("normalized_media_type") or "Unknown"
        format_rates[media_type] += rate
        format_counts[media_type] += 1
        category = post.get("content_category") or post.get("primary_content_category") or "General"
        category_rates[category] += rate
        category_counts[category] += 1

    top_formats = [
        {
            "format": _title_label(fmt),
            "average_engagement": round(format_rates[fmt] / max(format_counts[fmt], 1), 1),
            "market_share": _pct_score((format_counts[fmt] / total_posts) * 100),
        }
        for fmt, _ in format_counts.most_common(5)
    ]
    top_categories = [
        {
            "category": _title_label(category),
            "average_engagement": round(category_rates[category] / max(category_counts[category], 1), 1),
        }
        for category, _ in category_counts.most_common(5)
    ]
    return {
        "question": "What content performs best?",
        "top_formats": top_formats,
        "top_categories": top_categories,
    }


def _posts_per_week(posts: list[dict[str, Any]]) -> float:
    timestamps = [parse_timestamp(post.get("timestamp")) for post in posts]
    timestamps = [ts for ts in timestamps if ts]
    if len(timestamps) < 2:
        return round(len(posts) / 4, 1) if posts else 0.0
    timestamps.sort()
    span_days = max((timestamps[-1] - timestamps[0]).days, 1)
    return round(len(posts) / max(span_days / 7, 1), 1)


def _posting_timing(posts: list[dict[str, Any]]) -> tuple[list[str], str]:
    day_counts: Counter[str] = Counter()
    hour_counts: Counter[int] = Counter()
    for post in posts:
        ts = parse_timestamp(post.get("timestamp"))
        if not ts:
            continue
        day_counts[_WEEKDAYS[ts.weekday()]] += 1
        hour_counts[ts.hour] += 1
    best_days = [day for day, _ in day_counts.most_common(2)]
    if not hour_counts:
        return best_days, "10:00 AM - 12:00 PM"
    peak_hour = hour_counts.most_common(1)[0][0]
    start = datetime(2000, 1, 1, peak_hour)
    end = datetime(2000, 1, 1, min(peak_hour + 2, 23))
    window = f"{start.strftime('%I:%M %p').lstrip('0')} - {end.strftime('%I:%M %p').lstrip('0')}"
    return best_days, window


def _build_posting_behavior(
    *,
    company_analysis: dict[str, Any] | None,
    processed_posts: list[dict[str, Any]],
    content_mix: list[dict[str, Any]],
) -> dict[str, Any]:
    analysis = company_analysis or {}
    user_posts = (analysis.get("user_instagram") or {}).get("posts") or analysis.get("instagram_posts") or []
    user_rate = _posts_per_week(user_posts)

    competitor_rates: list[float] = []
    for profile in content_mix:
        posting = profile.get("posting_frequency") or {}
        rate = posting.get("posts_per_week")
        if rate is not None:
            competitor_rates.append(float(rate))
    if not competitor_rates and processed_posts:
        by_user: Counter[str] = Counter()
        for post in processed_posts:
            by_user[post.get("username") or "unknown"] += 1
        for username, count in by_user.items():
            user_posts_subset = [post for post in processed_posts if post.get("username") == username]
            competitor_rates.append(_posts_per_week(user_posts_subset if user_posts_subset else [{}] * count))

    market_avg = round(sum(competitor_rates) / max(len(competitor_rates), 1), 1) if competitor_rates else 0.0
    best_days, best_time = _posting_timing(processed_posts)
    return {
        "question": "How often do competitors publish?",
        "market_average_posts_per_week": market_avg,
        "your_posts_per_week": user_rate,
        "best_posting_days": best_days,
        "best_posting_time": best_time,
    }


def _human_signal_label(signal: str) -> str:
    mapping = {
        "hiring": "Hiring",
        "funding": "Funding activity",
        "expansion": "Expansion",
        "partnerships": "Enterprise partnerships",
        "posting_cadence": "High posting cadence",
        "audience_scale": "Strong audience scale",
        "engagement": "Strong engagement",
        "thought_leadership": "Weekly thought leadership",
    }
    return mapping.get(signal, _title_label(signal))


def _build_growth_signals(
    *,
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    analysis = company_analysis or {}
    user_followers = float(((analysis.get("user_instagram") or {}).get("instagram") or {}).get("followers") or 0)
    leaders: list[dict[str, Any]] = []

    for comp in competitors:
        name = _competitor_name(comp)
        ig = comp.get("instagram_analysis") or {}
        li = comp.get("linkedin_analysis") or {}
        followers = float(comp.get("followers") or ig.get("followers") or 0)
        jobs = len(comp.get("job_openings") or li.get("job_openings") or [])
        text = collect_text_blobs(comp)
        signals_raw = extract_business_signals(text)["active_signals"]
        score = 0.0
        signal_labels: list[str] = []

        if jobs >= 3 or li.get("is_hiring") or comp.get("is_hiring"):
            score += 25
            signal_labels.append("Hiring")
        if "funding" in signals_raw:
            score += 20
            signal_labels.append("Funding activity")
        if "expansion" in signals_raw:
            score += 15
            signal_labels.append("Expansion")
        if "partnerships" in signals_raw:
            score += 12
            signal_labels.append("Enterprise partnerships")
        engagement = float(ig.get("avg_engagement_rate") or (comp.get("content_strategy") or {}).get("avg_engagement_rate") or 0)
        if engagement >= 3.0:
            score += 15
            signal_labels.append("Strong engagement")
        if float(li.get("thought_leadership_score") or 0) >= 0.5:
            score += 10
            signal_labels.append("Weekly thought leadership")
        posting = ig.get("posting_frequency") or (comp.get("content_strategy") or {}).get("posting_frequency") or {}
        if float(posting.get("posts_per_week") or 0) >= 3:
            score += 8
            signal_labels.append("High posting cadence")
        if followers and user_followers and followers > user_followers * 1.3:
            score += 8
            signal_labels.append("Larger social audience")

        if score > 0:
            leaders.append(
                {
                    "company": name,
                    "growth_score": _pct_score(score),
                    "signals": signal_labels[:5],
                }
            )

    leaders.sort(key=lambda row: row["growth_score"], reverse=True)
    return {
        "question": "Which competitors are growing fastest?",
        "leaders": leaders[:8],
    }


def _extract_topics(text: str) -> set[str]:
    topics = {match.group(0).lower() for match in _TOPIC_RE.finditer(text or "")}
    for theme in re.findall(r"#(\w+)", text or ""):
        if len(theme) >= 3:
            topics.add(theme.lower())
    return topics


def _build_content_gap(
    *,
    company_analysis: dict[str, Any] | None,
    processed_posts: list[dict[str, Any]],
    market_insights: dict[str, Any] | None,
) -> dict[str, Any]:
    analysis = company_analysis or {}
    user_posts = (analysis.get("user_instagram") or {}).get("posts") or analysis.get("instagram_posts") or []
    user_topics: Counter[str] = Counter()
    for post in user_posts:
        for topic in _extract_topics((post.get("caption") or "") + " " + " ".join(post.get("hashtags") or [])):
            user_topics[topic] += 1

    competitor_topics: Counter[str] = Counter()
    for post in processed_posts:
        for topic in _extract_topics((post.get("caption") or "") + " " + " ".join(post.get("hashtags") or [])):
            competitor_topics[topic] += 1

    for row in (market_insights or {}).get("dominant_themes") or []:
        theme = str(row.get("theme") or "").lower().strip()
        if theme:
            competitor_topics[theme] += int(row.get("count") or 1)

    items: list[dict[str, Any]] = []
    for topic, comp_count in competitor_topics.most_common(15):
        your_count = user_topics.get(topic, 0)
        if comp_count >= 2 and your_count < max(comp_count // 3, 1):
            items.append(
                {
                    "topic": _title_label(topic),
                    "competitor_posts": comp_count,
                    "your_posts": your_count,
                    "priority": _priority_label(comp_count, max(sum(competitor_topics.values()), 1)),
                }
            )

    return {
        "question": "What topics are competitors covering that you are not?",
        "items": items[:10],
    }


def _build_seo_gap(
    *,
    gap_analysis: dict[str, Any],
    search_intelligence: dict[str, Any] | None,
    company_profile: dict[str, Any],
    intel_gaps: dict[str, Any],
) -> dict[str, Any]:
    search = search_intelligence or {}
    user_keywords = {str(item).lower() for item in (company_profile.get("keywords") or []) if item}
    missing: list[str] = []

    for keyword in gap_analysis.get("keyword_gaps") or []:
        label = _title_label(str(keyword))
        if label and label.lower() not in user_keywords:
            missing.append(label)

    for term in (search.get("product_terms") or []) + (search.get("industry_terms") or []):
        label = _title_label(str(term))
        if label and label.lower() not in user_keywords and label not in missing:
            missing.append(label)

    for row in intel_gaps.get("services") or []:
        label = _title_label(row.get("item") if isinstance(row, dict) else str(row))
        if label and label not in missing:
            missing.append(label)

    return {
        "question": "Which keywords are competitors ranking for?",
        "missing_keywords": missing[:12],
    }


def _build_opportunities(
    *,
    missing_services: dict[str, Any],
    technology_gap: dict[str, Any],
    content_gap: dict[str, Any],
    content_strategy: dict[str, Any],
    posting_behavior: dict[str, Any],
    best_channels: dict[str, Any],
    swot: dict[str, Any] | None,
) -> dict[str, Any]:
    high: list[str] = []
    medium: list[str] = []

    for item in missing_services.get("items") or []:
        if item.get("priority") == "High":
            high.append(f"Introduce {item.get('service')}")
        else:
            medium.append(f"Evaluate {item.get('service')}")

    for item in content_gap.get("items") or []:
        if item.get("priority") == "High":
            high.append(f"Publish {item.get('topic')} case studies")
        else:
            medium.append(f"Create content about {item.get('topic')}")

    top_format = (content_strategy.get("top_formats") or [{}])[0].get("format")
    if top_format:
        high.append(f"Create short-form {top_format}")

    if posting_behavior.get("your_posts_per_week", 0) < posting_behavior.get("market_average_posts_per_week", 0):
        winner = best_channels.get("winner") or "LinkedIn"
        high.append(f"Increase {winner} posting frequency")

    for item in technology_gap.get("items") or []:
        if item.get("priority") == "High":
            high.append(f"Highlight {item.get('technology')} capability")
        else:
            medium.append(f"Explore {item.get('technology')}")

    for item in (swot or {}).get("opportunities") or []:
        medium.append(str(item))

    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(item)
        return output

    return {
        "high_priority": _dedupe(high)[:8],
        "medium_priority": _dedupe(medium)[:8],
    }


def _build_threats(
    *,
    competitors: list[dict[str, Any]],
    growth_signals: dict[str, Any],
    intel_report: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    similarity_rows = intel_report.get("similarity_vs_competitors") or []

    for leader in (growth_signals.get("leaders") or [])[:5]:
        company = leader.get("company")
        signals = leader.get("signals") or []
        if company and signals:
            items.append(
                {
                    "competitor": company,
                    "reason": f"Driven by {', '.join(signals[:3]).lower()}",
                }
            )

    for row in sorted(
        similarity_rows,
        key=lambda item: float((item.get("similarity") or {}).get("overall") or 0),
        reverse=True,
    )[:3]:
        name = row.get("name")
        score = float((row.get("similarity") or {}).get("overall") or 0)
        if not name:
            continue
        comp = next((c for c in competitors if _competitor_name(c) == name), {})
        reasons: list[str] = []
        if score >= 0.65:
            reasons.append("high market overlap")
        engagement = float((comp.get("instagram_analysis") or {}).get("avg_engagement_rate") or 0)
        if engagement >= 3.5:
            reasons.append("higher engagement")
        specialties = (comp.get("linkedin_analysis") or {}).get("specialties") or []
        if len(specialties) >= 4:
            reasons.append("broader service portfolio")
        if reasons and not any(item.get("competitor") == name for item in items):
            items.append({"competitor": name, "reason": _title_label(reasons[0]) if len(reasons) == 1 else ", ".join(reasons).capitalize()})

    return {"items": items[:6]}


def _build_executive_summary(
    *,
    market_position: dict[str, Any],
    missing_services: dict[str, Any],
    content_gap: dict[str, Any],
    posting_behavior: dict[str, Any],
    growth_signals: dict[str, Any],
    threats: dict[str, Any],
    swot: dict[str, Any] | None,
    content_score: int,
) -> dict[str, Any]:
    strengths = list((swot or {}).get("strengths") or [])[:4]
    weaknesses = list((swot or {}).get("weaknesses") or [])[:4]

    if market_position.get("engagement_vs_market", 0) >= 0 and "Strong engagement quality" not in strengths:
        strengths.append("Good engagement quality")
    if market_position.get("content_score", 0) >= 60 and "Strong content relevance" not in strengths:
        strengths.append("Strong AI positioning" if content_score >= 65 else "Solid content relevance")

    if missing_services.get("total_missing", 0) >= 3 and "Limited service portfolio" not in weaknesses:
        weaknesses.append("Limited service portfolio")
    if posting_behavior.get("your_posts_per_week", 0) < posting_behavior.get("market_average_posts_per_week", 0):
        weaknesses.append("Low publishing frequency")

    biggest_opportunity = None
    content_items = content_gap.get("items") or []
    service_items = missing_services.get("items") or []
    if content_items:
        biggest_opportunity = content_items[0].get("topic")
    elif service_items:
        biggest_opportunity = service_items[0].get("service")

    biggest_threat = None
    if threats.get("items"):
        biggest_threat = threats["items"][0].get("competitor")
    elif growth_signals.get("leaders"):
        biggest_threat = growth_signals["leaders"][0].get("company")

    score = _pct_score(
        market_position.get("market_percentile", 0) * 0.35
        + market_position.get("content_score", 0) * 0.25
        + market_position.get("service_coverage", 0) * 0.15
        + market_position.get("technology_coverage", 0) * 0.1
        + market_position.get("brand_visibility", 0) * 0.15
    )

    return {
        "score": score,
        "strengths": strengths[:4],
        "weaknesses": weaknesses[:4],
        "biggest_opportunity": biggest_opportunity,
        "biggest_threat": biggest_threat,
    }


def build_strategic_insights(
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any] | None,
    company_analysis: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
    competitor_intelligence_report: dict[str, Any] | None,
    gap_analysis: dict[str, Any] | None,
    search_intelligence: dict[str, Any] | None,
    processed_posts: list[dict[str, Any]],
    content_mix: list[dict[str, Any]],
    market_insights: dict[str, Any] | None = None,
    swot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical strategic_insights object for the competitor dashboard."""
    intel = competitor_intelligence_report or {}
    gaps_raw = gap_analysis or {}
    intel_gaps = intel.get("gaps") or {}
    profile = company_profile or {}

    user_services = _user_service_set(company, profile)
    user_tech = _user_tech_set(profile)
    market_services: set[str] = set()
    market_tech: set[str] = set()
    for comp in competitors:
        market_services.update(str(item).lower().strip() for item in _service_terms(comp))
        market_tech.update(str(item).lower().strip() for item in _technology_terms(comp))

    coverage = {
        "service": _coverage_pct(user_services, market_services),
        "technology": _coverage_pct(user_tech, market_tech),
    }

    content_strategy = _build_content_strategy(processed_posts=processed_posts)
    top_content_engagement = (
        (content_strategy.get("top_formats") or [{}])[0].get("average_engagement") or 0
    )
    content_score = _pct_score(min(float(top_content_engagement) * 12, 100)) if top_content_engagement else 50

    missing_services = _build_missing_services(
        competitors=competitors,
        company=company,
        company_profile=profile,
        intel_gaps=intel_gaps,
        gap_analysis=gaps_raw,
    )
    technology_gap = _build_technology_gap(
        competitors=competitors,
        company_profile=profile,
        intel_gaps=intel_gaps,
        gap_analysis=gaps_raw,
    )
    best_social_channels = _build_best_social_channels(
        company_analysis=company_analysis,
        competitors=competitors,
    )
    posting_behavior = _build_posting_behavior(
        company_analysis=company_analysis,
        processed_posts=processed_posts,
        content_mix=content_mix,
    )
    growth_signals = _build_growth_signals(
        company_analysis=company_analysis,
        competitors=competitors,
    )
    content_gap = _build_content_gap(
        company_analysis=company_analysis,
        processed_posts=processed_posts,
        market_insights=market_insights,
    )
    seo_gap = _build_seo_gap(
        gap_analysis=gaps_raw,
        search_intelligence=search_intelligence,
        company_profile=profile,
        intel_gaps=intel_gaps,
    )
    market_position = _build_market_position(
        company=company,
        company_profile=profile,
        company_analysis=company_analysis,
        competitors=competitors,
        intel_report=intel,
        coverage=coverage,
        content_score=content_score,
    )
    threats = _build_threats(
        competitors=competitors,
        growth_signals=growth_signals,
        intel_report=intel,
    )
    opportunities = _build_opportunities(
        missing_services=missing_services,
        technology_gap=technology_gap,
        content_gap=content_gap,
        content_strategy=content_strategy,
        posting_behavior=posting_behavior,
        best_channels=best_social_channels,
        swot=swot,
    )
    executive_summary = _build_executive_summary(
        market_position=market_position,
        missing_services=missing_services,
        content_gap=content_gap,
        posting_behavior=posting_behavior,
        growth_signals=growth_signals,
        threats=threats,
        swot=swot,
        content_score=content_score,
    )


    customer_insights = build_customer_insights(
        company=company,
        company_profile=profile,
        company_analysis=company_analysis,
        competitors=competitors,
        competitor_intelligence_report=intel,
        gap_analysis=gaps_raw,
        content_mix=content_mix,
        market_position=market_position,
        region=company.get("region") or profile.get("region"),
    )

    return {
        "missing_services": missing_services,
        "technology_gap": technology_gap,
        "market_position": market_position,
        "best_social_channels": best_social_channels,
        "content_strategy": content_strategy,
        "posting_behavior": posting_behavior,
        "growth_signals": growth_signals,
        "content_gap": content_gap,
        "seo_gap": seo_gap,
        "opportunities": opportunities,
        "threats": threats,
        "executive_summary": executive_summary,
        "customer_insights": customer_insights,
    }
