from agents.trend.state.trend_state import TrendState

DISCOVERY_LABELS = {
    "instagram_search": "Instagram live search",
    "seed_usernames": "provided usernames",
    "database": "database",
    "smart_competitor_search": "smart competitor search",
    "manual_competitors": "manual competitors",
    "web_trend_crawl": "web trend sources",
}

PLATFORM_LABELS = {
    "reddit": "Reddit",
    "x": "X",
    "facebook": "Facebook",
    "linkedin": "LinkedIn",
    "google": "Google Trends",
    "web": "Web blogs",
    "tavily": "Tavily search",
}


def _format_google_trends_by_country(
    top_by_country: dict[str, dict],
    rising_by_country: dict[str, dict],
) -> list[str]:
    lines: list[str] = []
    for label in top_by_country:
        top = [
            item.get("query") or item.get("topic")
            for item in (top_by_country.get(label) or {}).get("queries") or []
            if item.get("query") or item.get("topic")
        ][:3]
        rising = [
            item.get("query") or item.get("topic")
            for item in (rising_by_country.get(label) or {}).get("queries") or []
            if item.get("query") or item.get("topic")
        ][:3]
        if top:
            lines.append(f"{label} top: {', '.join(top)}.")
        if rising:
            lines.append(f"{label} rising: {', '.join(rising)}.")
    return lines


def _format_source_attribution(
    source_breakdown: list[dict],
    platform_summary: dict[str, dict],
) -> list[str]:
    lines: list[str] = []
    if platform_summary:
        for platform, data in platform_summary.items():
            label = PLATFORM_LABELS.get(platform, platform.title())
            highlights = data.get("highlights") or []
            if not highlights:
                continue
            preview = ", ".join(str(item) for item in highlights[:3])
            lines.append(f"{label}: {preview}.")
        return lines

    for entry in source_breakdown[:6]:
        source = entry.get("source") or "Unknown"
        highlights: list[str] = []
        for topic in entry.get("topics") or []:
            if topic.get("topic"):
                highlights.append(str(topic["topic"]))
        for tag in entry.get("hashtags") or []:
            if tag.get("tag"):
                highlights.append(f"#{tag['tag']}")
        for fmt in entry.get("reel_formats") or []:
            if fmt.get("name"):
                highlights.append(str(fmt["name"]))
        if highlights:
            lines.append(f"{source}: {', '.join(highlights[:3])}.")
    return lines


async def GenerateTrendSummaryNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    agent_mode = config.get("agent_mode") or "trend"
    web_trends = state.get("web_trends") or {}
    web_crawl = state.get("web_crawl") or {}

    if agent_mode == "global_trend":
        sources = config.get("web_sources") or web_crawl.get("sources") or []
        formats = web_trends.get("reel_formats") or []
        hashtags = web_trends.get("hashtags") or []
        topics = web_trends.get("topics") or []
        google_trends = web_trends.get("google_trends") or []
        source_breakdown = web_trends.get("source_breakdown") or web_crawl.get("source_breakdown") or []
        platform_summary = web_crawl.get("platform_summary") or {}

        lines = [
            "Instagram trends today (web sources + Google Trends + Reddit + X + Facebook + LinkedIn).",
            f"Scanned {len(sources)} sources including blogs, Google Trends, Reddit, X, Facebook, and LinkedIn.",
        ]
        if formats:
            names = ", ".join(item.get("name") for item in formats[:4] if item.get("name"))
            lines.append(f"Trending Reel formats: {names}.")
        if hashtags:
            tags = ", ".join(f"#{item.get('hashtag') or item.get('tag')}" for item in hashtags[:5])
            lines.append(f"Popular hashtags: {tags}.")
        country_lines = _format_google_trends_by_country(
            web_trends.get("top_queries_by_country")
            or web_crawl.get("top_queries_by_country")
            or {},
            web_trends.get("rising_queries_by_country")
            or web_crawl.get("rising_queries_by_country")
            or {},
        )
        if country_lines:
            lines.append("Google Trends by country: " + " ".join(country_lines[:6]))
        elif google_trends:
            rising = ", ".join(
                item.get("topic") or item.get("key")
                for item in google_trends[:5]
                if item.get("topic") or item.get("key")
            )
            lines.append(f"Google Trends searches: {rising}.")
        if topics:
            topic_names = ", ".join(item.get("topic") or item.get("key") for item in topics[:3])
            lines.append(f"Cultural topics: {topic_names}.")

        source_lines = _format_source_attribution(source_breakdown, platform_summary)
        if source_lines:
            lines.append("By source: " + " ".join(source_lines))

        if not formats and not hashtags:
            lines.append("Limited trend signals extracted; check source connectivity.")
        state["trend_summary"] = " ".join(lines)
        return state

    company = config.get("company") or {}
    company_analysis = state.get("company_analysis") or {}
    company_name = company.get("name") or config.get("company_name") or "the company"
    detected_category = config.get("detected_category") or config.get("category") or company_analysis.get("detected_niche")
    region = config.get("region") or (config.get("filters") or {}).get("region") or "target region"
    discovery_source = config.get("discovery_source") or "instagram_search"
    discovery_label = DISCOVERY_LABELS.get(discovery_source, discovery_source)

    handles = company_analysis.get("social_handles") or {}
    ig_user = handles.get("instagram_username") or company.get("instagram_username")
    li_url = handles.get("linkedin_url") or company.get("linkedin_url")
    instagram_insights = company_analysis.get("instagram") or {}
    pain_points = state.get("pain_points") or company_analysis.get("pain_points") or []

    top_trends = (state.get("trend_scores") or [])[:5]
    top_hashtags = [item for item in top_trends if item.get("group_type") == "hashtag"][:3]
    top_topics = [item for item in top_trends if item.get("group_type") == "topic"][:3]
    top_formats = [item for item in top_trends if item.get("group_type") == "reel_format"][:3]
    viral_count = len(state.get("viral_posts") or [])
    post_count = len(state.get("processed_posts") or [])
    company_post_count = len(state.get("company_posts") or [])
    linkedin_post_count = len(state.get("linkedin_posts") or [])
    competitor_count = len(state.get("discovered_influencers") or [])
    content_mix = state.get("content_mix") or []
    lines = [
        f"Instagram trend analysis for {company_name} ({detected_category or 'industry'}) in {region}.",
    ]
    if ig_user:
        lines.append(
            f"Company Instagram @{ig_user}: {company_post_count} posts analyzed; "
            f"niche={instagram_insights.get('detected_niche') or detected_category or 'unknown'}; "
            f"primary format={instagram_insights.get('primary_format') or 'unknown'}."
        )
    if li_url:
        lines.append(
            f"LinkedIn scanned ({linkedin_post_count} posts). "
            f"Themes: {', '.join(company_analysis.get('linkedin_content_themes') or [])[:3] or ['general business content']}."
        )
    if pain_points:
        pp = ", ".join(item.get("pain_point") for item in pain_points[:3] if item.get("pain_point"))
        lines.append(f"Detected audience pain points: {pp}.")
    lines.append(f"Analyzed {competitor_count} competitor account(s) via {discovery_label}.")
    lines.append(f"Processed {post_count} competitor posts; flagged {viral_count} viral posts.")

    if top_hashtags:
        tags = ", ".join(f"#{item['key']}" for item in top_hashtags)
        lines.append(f"Trending hashtags: {tags}.")
    if top_formats:
        formats = ", ".join(item["key"] for item in top_formats)
        lines.append(f"Trending Reel formats in your niche: {formats}.")
    elif top_topics:
        topics = ", ".join(item["key"] for item in top_topics)
        lines.append(f"Trending topics: {topics}.")
    source_breakdown = web_trends.get("source_breakdown") or []
    if source_breakdown:
        social_lines = _format_source_attribution(source_breakdown, {})
        if social_lines:
            lines.append("Web sources contributed: " + " ".join(social_lines[:4]))

    if content_mix:
        reels_leader = max(
            content_mix,
            key=lambda profile: next(
                (
                    item.get("share_pct", 0)
                    for item in profile.get("media_types", [])
                    if item.get("type") == "Reels"
                ),
                0,
            ),
            default=None,
        )
        if reels_leader:
            username = reels_leader.get("username")
            reels_pct = next(
                (
                    item.get("share_pct")
                    for item in reels_leader.get("media_types", [])
                    if item.get("type") == "Reels"
                ),
                None,
            )
            if username and reels_pct:
                lines.append(f"@{username} leads on Reels ({reels_pct}% of their posts).")

    if not top_hashtags and not top_topics and not top_formats:
        lines.append("No strong hashtag or topic clusters detected in this run.")

    state["trend_summary"] = " ".join(lines)
    return state
