
from __future__ import annotations
import re
from collections import Counter, defaultdict
from typing import Any
from service.Competitor.openai_client import chat_completion_json


def _title(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    if text.lower() in {"ai", "ml", "ui", "ux", "b2b", "saas"}:
        return text.upper()
    return text[0].upper() + text[1:]


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _engagement(post: dict[str, Any]) -> float:
    if post.get("engagement_rate") is not None:
        try:
            return float(post["engagement_rate"])
        except (TypeError, ValueError):
            pass
    followers = max(int(post.get("followers") or 0), 1)
    likes = int(post.get("likes") or post.get("like_count") or 0)
    comments = int(post.get("comments") or post.get("comments_count") or 0)
    return round(((likes + comments) / followers) * 100, 4)


def _format_label(post: dict[str, Any]) -> str:
    media = str(post.get("media_type") or post.get("format") or post.get("normalized_media_type") or "").lower()
    product = str(post.get("media_product_type") or "").lower()
    if "reel" in media or product == "reels" or media in {"video", "reel", "reels"}:
        return "reel"
    if "carousel" in media:
        return "carousel"
    if media in {"image", "photo"}:
        return "image"
    if post.get("format"):
        return str(post["format"]).strip().lower()
    return "post"


def _topic_label(post: dict[str, Any]) -> str:
    topic = post.get("topic") or post.get("content_category") or post.get("primary_content_category")
    if topic and str(topic).strip().lower() not in {"", "general", "unknown"}:
        return _title(topic)
    text = f"{post.get('caption') or ''} {' '.join(post.get('hashtags') or [])}".lower()
    for label, pattern in (
        ("AI", r"\b(ai|machine learning|llm|agents?)\b"),
        ("Case Studies", r"\b(case stud|client success|customer story)\b"),
        ("Cloud", r"\b(cloud|devops|migration)\b"),
        ("Automation", r"\b(automat|workflow|rpa)\b"),
    ):
        if re.search(pattern, text, re.I):
            return label
    return "General"


def _collect_user_posts(company_analysis: dict[str, Any], competitor_analysis: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    analysis = company_analysis or {}
    competitor = competitor_analysis or {}
    user_ig = ((analysis.get("user_instagram") or {}) if isinstance(analysis.get("user_instagram"), dict) else {})
    user_li = ((analysis.get("user_linkedin") or {}) if isinstance(analysis.get("user_linkedin"), dict) else {})

    ig_posts = list(user_ig.get("posts") or analysis.get("instagram_posts") or [])
    li_posts = list(user_li.get("linkedin_posts") or analysis.get("linkedin_posts") or [])

    if not ig_posts:
        company_block = competitor.get("company_analysis") or {}
        ig_posts = list(((company_block.get("user_instagram") or {}).get("posts")) or [])
    if not li_posts:
        company_block = competitor.get("company_analysis") or {}
        li_posts = list(((company_block.get("user_linkedin") or {}).get("linkedin_posts")) or [])

    return {"instagram": ig_posts, "linkedin": li_posts}


def _platform_performance(posts: list[dict[str, Any]]) -> dict[str, Any]:
    rates = [_engagement(p) for p in posts]
    by_format: dict[str, list[float]] = defaultdict(list)
    by_topic: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        by_format[_format_label(post)].append(_engagement(post))
        by_topic[_topic_label(post)].append(_engagement(post))

    best_formats = sorted(
        (
            {"format": fmt, "engagement_rate": _avg(vals), "post_count": len(vals)}
            for fmt, vals in by_format.items()
        ),
        key=lambda row: row["engagement_rate"],
        reverse=True,
    )[:5]
    best_topics = sorted(
        (
            {"topic": topic, "engagement_rate": _avg(vals), "post_count": len(vals)}
            for topic, vals in by_topic.items()
        ),
        key=lambda row: row["engagement_rate"],
        reverse=True,
    )[:5]
    best_posts = sorted(
        (
            {
                "caption": (post.get("caption") or "")[:160],
                "format": _format_label(post),
                "topic": _topic_label(post),
                "engagement_rate": _engagement(post),
                "url": post.get("url") or post.get("permalink") or post.get("post_url"),
            }
            for post in posts
        ),
        key=lambda row: row["engagement_rate"],
        reverse=True,
    )[:5]

    return {
        "average_engagement_rate": _avg(rates),
        "best_formats": best_formats,
        "best_topics": best_topics,
        "best_posts": best_posts,
        "posting_frequency": round(len(posts) / 4, 2) if posts else 0.0,
        "post_count": len(posts),
    }


def build_social_performance(
    *,
    company_analysis: dict[str, Any] | None = None,
    competitor_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    posts = _collect_user_posts(company_analysis or {}, competitor_analysis or {})
    return {
        "instagram": _platform_performance(posts["instagram"]),
        "linkedin": _platform_performance(posts["linkedin"]),
    }


def _competitor_posts(competitor_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for post in competitor_analysis.get("processed_posts") or []:
        posts.append(post)
    for comp in competitor_analysis.get("competitors") or []:
        for post in comp.get("posts") or []:
            posts.append({**post, "username": comp.get("username") or comp.get("name")})
        for post in ((comp.get("linkedin_analysis") or {}).get("posts") or []):
            posts.append({**post, "platform": "linkedin"})
    return posts


def build_competitor_content(
    *,
    competitor_analysis: dict[str, Any] | None = None,
    content_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intel = content_intelligence or {}
    competitor = competitor_analysis or {}
    posts = _competitor_posts(competitor)

    topic_counts = Counter(_topic_label(p) for p in posts)
    format_counts = Counter(_format_label(p) for p in posts)

    top_topics = [
        {"topic": topic, "count": count, "share_pct": round(100 * count / max(len(posts), 1), 1)}
        for topic, count in topic_counts.most_common(8)
    ]
    top_formats = [
        {"format": fmt, "count": count, "share_pct": round(100 * count / max(len(posts), 1), 1)}
        for fmt, count in format_counts.most_common(8)
    ]

    if intel.get("top_topics") and not top_topics:
        top_topics = [
            {
                "topic": row.get("topic") if isinstance(row, dict) else str(row),
                "count": (row.get("competitor_posts") if isinstance(row, dict) else None) or 0,
                "share_pct": (row.get("competitor_usage_pct") if isinstance(row, dict) else None) or 0,
            }
            for row in intel.get("top_topics") or []
        ]
    if intel.get("top_formats") and not top_formats:
        top_formats = [
            {
                "format": row.get("format") if isinstance(row, dict) else str(row),
                "count": (row.get("competitor_posts") if isinstance(row, dict) else None) or 0,
                "share_pct": (row.get("competitor_usage_pct") if isinstance(row, dict) else None) or 0,
            }
            for row in intel.get("top_formats") or []
        ]

    gaps = []
    for row in intel.get("content_opportunities") or []:
        if isinstance(row, dict):
            gaps.append(
                {
                    "topic": row.get("topic") or row.get("item") or row.get("opportunity"),
                    "type": row.get("type") or "opportunity",
                    "reason": row.get("reason") or row.get("insight") or "Competitor content gap",
                }
            )
    for row in (competitor.get("competitive_gaps") or {}).get("content_gaps") or []:
        if isinstance(row, dict):
            gaps.append(
                {
                    "topic": row.get("item") or row.get("topic") or row.get("gap"),
                    "type": "content_gap",
                    "reason": row.get("reason") or "Underused vs competitors",
                }
            )

    overused = [row["topic"] for row in top_topics[:3] if float(row.get("share_pct") or 0) >= 20]

    patterns = []
    if top_formats:
        patterns.append(f"Competitors lean on {top_formats[0]['format']} content")
    if top_topics:
        patterns.append(f"Most discussed topic: {top_topics[0]['topic']}")
    if posts:
        patterns.append(f"Analyzed {len(posts)} competitor posts")

    return {
        "competitor_content_patterns": patterns,
        "top_competitor_topics": top_topics,
        "top_competitor_formats": top_formats,
        "content_gaps": gaps[:12],
        "overused_topics": overused,
        "posting_frequency": round(len(posts) / max(len(competitor.get("competitors") or [1]), 1) / 4, 2),
        "engagement": {
            "average_engagement_rate": _avg([_engagement(p) for p in posts]),
        },
        "content_pillars": [row["topic"] for row in top_topics[:5]],
        "hooks": [],
        "ctas": [],
        "messaging": [],
        "services_promoted": [],
        "audience_addressed": [],
        "content_themes": [row["topic"] for row in top_topics[:6]],
    }


def build_content_opportunities(
    *,
    company: dict[str, Any],
    company_dna: dict[str, Any],
    social_performance: dict[str, Any],
    competitor_content: dict[str, Any],
    content_intelligence: dict[str, Any] | None = None,
    business_goals: list[str] | None = None,
) -> dict[str, Any]:
    services = list(company.get("services") or company_dna.get("services") or [])
    expertise = [_title(s) for s in services][:8]
    opportunities: list[dict[str, Any]] = []

    for row in (content_intelligence or {}).get("content_opportunities") or []:
        if not isinstance(row, dict):
            continue
        topic = row.get("topic") or row.get("item") or row.get("opportunity")
        if not topic:
            continue
        opportunities.append(
            {
                "topic": _title(topic),
                "reason": row.get("reason") or row.get("insight") or "Identified from competitor content intelligence",
                "priority": int(row.get("priority_score") or row.get("priority") or 80),
                "recommended_formats": list(row.get("recommended_formats") or row.get("formats") or ["LinkedIn carousel", "Instagram reel"]),
            }
        )

    for gap in competitor_content.get("content_gaps") or []:
        topic = gap.get("topic") if isinstance(gap, dict) else str(gap)
        if not topic:
            continue
        if any(o["topic"].lower() == str(topic).lower() for o in opportunities):
            continue
        opportunities.append(
            {
                "topic": _title(topic),
                "reason": (gap.get("reason") if isinstance(gap, dict) else None)
                or "Strong service alignment but low competitor coverage",
                "priority": 88,
                "recommended_formats": ["Case study", "LinkedIn document"],
            }
        )

    for topic in expertise:
        if any(o["topic"].lower() == topic.lower() for o in opportunities):
            continue
        aligned = any(topic.lower() in str(t.get("topic") or "").lower() for t in competitor_content.get("top_competitor_topics") or [])
        opportunities.append(
            {
                "topic": topic,
                "reason": (
                    "High competitor activity + strong alignment with company expertise"
                    if aligned
                    else "Matches company expertise and business goals"
                ),
                "priority": 92 if aligned else 84,
                "recommended_formats": ["LinkedIn carousel", "Instagram reel"],
            }
        )

    ig_topics = (social_performance.get("instagram") or {}).get("best_topics") or []
    for row in ig_topics[:3]:
        topic = row.get("topic")
        if not topic or any(o["topic"].lower() == str(topic).lower() for o in opportunities):
            continue
        opportunities.append(
            {
                "topic": _title(topic),
                "reason": f"Already performing well on Instagram ({row.get('engagement_rate')}% ER)",
                "priority": 86,
                "recommended_formats": ["Instagram reel", "Carousel"],
            }
        )

    if business_goals and not opportunities:
        opportunities.append(
            {
                "topic": "Thought leadership",
                "reason": f"Supports goal: {business_goals[0]}",
                "priority": 80,
                "recommended_formats": ["LinkedIn post", "Instagram carousel"],
            }
        )

    opportunities.sort(key=lambda row: int(row.get("priority") or 0), reverse=True)
    return {"opportunities": opportunities[:12]}


def build_content_strategy(
    *,
    company: dict[str, Any],
    company_dna: dict[str, Any],
    opportunities: dict[str, Any],
    business_goals: list[str] | None = None,
) -> dict[str, Any]:
    goals = business_goals or ["Generate qualified B2B leads"]
    primary_goal = goals[0]
    name = company.get("name") or company_dna.get("name") or "the company"
    industry = company.get("industry") or company_dna.get("industry") or "B2B technology"
    top_topics = [o.get("topic") for o in (opportunities.get("opportunities") or [])[:3] if o.get("topic")]

    pillars = [
        {"name": "AI Education" if any("ai" in str(t).lower() for t in top_topics) else "Education", "percentage": 30, "objective": "Build authority"},
        {"name": "Case Studies", "percentage": 25, "objective": "Build trust"},
        {"name": "Technical Insights", "percentage": 20, "objective": "Demonstrate expertise"},
        {"name": "Company", "percentage": 15, "objective": "Humanize brand"},
        {"name": "Offers", "percentage": 10, "objective": "Generate leads"},
    ]
    if top_topics:
        pillars[0]["name"] = f"{top_topics[0]} Education" if "education" not in top_topics[0].lower() else top_topics[0]

    positioning = (
        f"{name} should position content as a practical {industry} authority — "
        f"educate first, prove results with case studies, then convert with soft offers."
    )
    return {
        "strategy": {
            "primary_goal": primary_goal,
            "content_positioning": positioning,
            "content_pillars": pillars,
            "focus_topics": top_topics,
            "business_goals": goals,
        }
    }


def build_platform_strategy(
    *,
    platforms: list[str] | None = None,
    content_strategy: dict[str, Any] | None = None,
    social_performance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested = [p.lower() for p in (platforms or ["linkedin", "instagram"])]
    strategy = (content_strategy or {}).get("strategy") or {}
    social = social_performance or {}

    linkedin = {
        "platform": "linkedin",
        "role": "Authority + B2B lead generation",
        "formats": ["Thought leadership", "Case studies", "Technical breakdowns", "Founder posts"],
        "content_ratio": {
            "educational": 40,
            "authority": 25,
            "case_study": 20,
            "promotional": 10,
            "company": 5,
        },
        "goal_alignment": strategy.get("primary_goal"),
        "best_performing": (social.get("linkedin") or {}).get("best_formats") or [],
    }
    instagram = {
        "platform": "instagram",
        "role": "Reach + brand awareness",
        "formats": ["Reels", "Carousels", "Stories"],
        "content_ratio": {
            "educational": 35,
            "entertainment": 25,
            "authority": 20,
            "case_study": 10,
            "promotional": 10,
        },
        "goal_alignment": strategy.get("primary_goal"),
        "best_performing": (social.get("instagram") or {}).get("best_formats") or [],
    }

    out: dict[str, Any] = {"platforms": []}
    if "linkedin" in requested:
        out["linkedin"] = linkedin
        out["platforms"].append(linkedin)
    if "instagram" in requested:
        out["instagram"] = instagram
        out["platforms"].append(instagram)
    return out


def _deterministic_ideas(
    *,
    company: dict[str, Any],
    opportunities: list[dict[str, Any]],
    strategy: dict[str, Any],
    platforms: list[str],
    idea_count: int,
) -> list[dict[str, Any]]:
    pillars = ((strategy.get("strategy") or {}).get("content_pillars") or [])
    audience = (company.get("target_audience") or ["SME founders"])
    audience_label = audience[0] if audience else "SME founders"
    ideas: list[dict[str, Any]] = []

    templates = [
        ("linkedin", "carousel", "Authority", "Most companies are using AI wrong...", "Comment 'AI' and I'll send you the framework."),
        ("instagram", "reel", "Reach", "Stop doing this with your content...", "Follow for more practical AI tips."),
        ("linkedin", "case study", "Trust", "We cut operational costs by 32% — here's how", "DM me 'CASE' for the breakdown."),
        ("instagram", "carousel", "Authority", "5 myths about AI agents", "Save this for your next planning session."),
        ("linkedin", "founder post", "Engagement", "What I wish I knew before building AI products", "What would you add?"),
    ]

    for index in range(idea_count):
        opp = opportunities[index % max(len(opportunities), 1)] if opportunities else {"topic": "Thought leadership", "priority": 80}
        platform, fmt, objective, hook, cta = templates[index % len(templates)]
        if platforms and platform not in platforms:
            platform = platforms[index % len(platforms)]
        pillar = pillars[index % len(pillars)] if pillars else {"name": "Education", "objective": objective}
        topic = opp.get("topic") or "Industry insights"
        ideas.append(
            {
                "title": f"{5 if index % 2 == 0 else 3} ways {topic} can reduce operational costs"
                if index % 3 == 0
                else f"{topic}: what {audience_label} need to know",
                "platform": platform,
                "format": fmt,
                "content_pillar": pillar.get("name") or "Education",
                "objective": pillar.get("objective") or objective,
                "target_audience": audience_label,
                "hook": hook,
                "angle": f"Practical angle on {topic} tied to business outcomes",
                "key_points": [
                    f"Define the problem {audience_label} face with {topic}",
                    "Show a concrete example or framework",
                    "End with a clear next step",
                ],
                "cta": cta,
                "reason": opp.get("reason") or "Matches company expertise + identified market opportunity",
                "priority_score": int(opp.get("priority") or 80) - (index % 5),
            }
        )
    return ideas


async def build_content_ideas(
    *,
    company: dict[str, Any],
    opportunities: dict[str, Any],
    content_strategy: dict[str, Any],
    platform_strategy: dict[str, Any],
    platforms: list[str] | None = None,
    idea_count: int = 10,
) -> list[dict[str, Any]]:
    requested = [p.lower() for p in (platforms or ["linkedin", "instagram"])]
    opps = list((opportunities or {}).get("opportunities") or [])
    fallback = _deterministic_ideas(
        company=company,
        opportunities=opps,
        strategy=content_strategy,
        platforms=requested,
        idea_count=idea_count,
    )

    try:
        payload = await chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a B2B content strategist. Return JSON only with key "
                        "`ideas` as an array of content idea objects. Each idea must include: "
                        "title, platform, format, content_pillar, objective, target_audience, "
                        "hook, angle, key_points (array), cta, reason, priority_score (number)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Company: {company}\n"
                        f"Opportunities: {opps[:8]}\n"
                        f"Strategy: {content_strategy}\n"
                        f"Platform strategy: {platform_strategy}\n"
                        f"Platforms: {requested}\n"
                        f"Generate {idea_count} high-priority content ideas."
                    ),
                },
            ],
            temperature=0.5,
        )
        ideas = payload.get("ideas") if isinstance(payload, dict) else None
        if isinstance(ideas, list) and ideas:
            cleaned = []
            for index, idea in enumerate(ideas[:idea_count]):
                if not isinstance(idea, dict):
                    continue
                base = fallback[index] if index < len(fallback) else fallback[0]
                cleaned.append({**base, **idea})
            if cleaned:
                return cleaned
    except Exception:
        pass

    return fallback


def build_content_calendar(
    *,
    content_ideas: list[dict[str, Any]],
    content_strategy: dict[str, Any] | None = None,
    calendar_days: int = 7,
    ninety_day_plan: dict[str, Any] | None = None,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministic calendar helper; prefers the agent node for LLM scheduling."""
    from agents.contentrecommendation.node.GenerateContentCalendarNode import (
        build_fallback_calendar,
    )

    return build_fallback_calendar(
        content_ideas=content_ideas,
        content_strategy=content_strategy,
        ninety_day_plan=ninety_day_plan,
        platforms=platforms,
        calendar_days=calendar_days,
        skip_weekends=calendar_days > 7,
    )


def build_recommendation_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy": state.get("content_strategy") or {},
        "platform_strategy": state.get("platform_strategy") or {},
        "content_ideas": state.get("content_ideas") or [],
        "content_calendar": state.get("content_calendar") or {},
    }


_PUBLIC_RESPONSE_DROP_KEYS = frozenset(
    {
        "social_performance",
        "competitor_content",
        "content_opportunities",
        "ninety_day_action_plan",
    }
)

_RECOMMENDATION_DROP_KEYS = frozenset(
    {
        "social_performance",
        "competitor_content",
        "opportunities",
        "ninety_day_action_plan",
    }
)


def sanitize_content_recommendation_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip diagnostic competitor/social/plan blocks from API-facing payloads."""
    cleaned = {key: value for key, value in payload.items() if key not in _PUBLIC_RESPONSE_DROP_KEYS}
    recommendation = dict(cleaned.get("recommendation") or {})
    for key in _RECOMMENDATION_DROP_KEYS:
        recommendation.pop(key, None)
    if recommendation:
        cleaned["recommendation"] = recommendation
    else:
        cleaned.pop("recommendation", None)
    return cleaned
