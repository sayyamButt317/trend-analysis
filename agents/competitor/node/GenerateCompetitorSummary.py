from agents.trend.services.content_analyzer import build_market_content_usage
from agents.trend.state.trend_state import TrendState


async def GenerateCompetitorSummaryNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    company = config.get("company") or {}
    company_name = company.get("name") or config.get("company_name") or "your company"
    industry = company.get("industry") or config.get("industry")
    country = company.get("country") or config.get("country")
    region = (config.get("filters") or config).get("region") or config.get("region")
    city = (config.get("filters") or config).get("city") or config.get("city")

    competitors = state.get("discovered_influencers") or []
    content_mix = state.get("content_mix") or []
    post_count = len(state.get("processed_posts") or [])

    lines = [
        f"Competitor analysis for {company_name}.",
    ]
    if industry:
        lines.append(f"Industry: {industry}.")
    location_parts = [part for part in [city, country, region] if part]
    if location_parts:
        lines.append(f"Region focus: {', '.join(location_parts)}.")
    lines.append(
        f"Smart-matched {len(competitors)} competitor account(s) and analyzed {post_count} posts."
    )

    for comp in competitors[:3]:
        score = comp.get("match_score")
        if score is not None:
            lines.append(f"@{comp.get('username')}: relevance score {score}.")

    for profile in content_mix[:5]:
        media_summary = ", ".join(
            f"{item['type']} {item['share_pct']}%"
            for item in profile.get("media_types") or []
        )
        theme_summary = ", ".join(
            f"{item['theme']} {item['share_pct']}%"
            for item in (profile.get("content_themes") or [])[:3]
        )
        lines.append(
            f"@{profile['username']}: {media_summary or 'no media mix'}. "
            f"Themes: {theme_summary or 'General'}."
        )
        category_summary = ", ".join(
            f"{item['category']} {item['share_pct']}%"
            for item in (profile.get("content_categories") or [])[:3]
        )
        if category_summary:
            lines.append(
                f"@{profile['username']} business content: {category_summary}."
            )

    if content_mix:
        usage = build_market_content_usage(content_mix, state.get("processed_posts") or [])
        if usage.get("summary"):
            lines.append(f"Overall content usage: {usage['summary']}")
    else:
        lines.append("No content mix could be computed from competitor posts.")

    state["competitor_summary"] = " ".join(lines)
    state["trend_summary"] = state["competitor_summary"]
    return state
