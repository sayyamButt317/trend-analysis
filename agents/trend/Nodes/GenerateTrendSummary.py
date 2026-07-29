from agents.trend.state.trend_state import TrendState

DISCOVERY_LABELS = {
    "instagram_search": "Instagram live search",
    "seed_usernames": "provided usernames",
    "database": "database",
    "smart_competitor_search": "smart competitor search",
    "manual_competitors": "manual competitors",
    "web_trend_crawl": "web trend sources",
}


async def GenerateTrendSummaryNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    agent_mode = config.get("agent_mode") or "trend"
    web_trends = state.get("web_trends") or {}

    if agent_mode == "global_trend":
        sources = config.get("web_sources") or (state.get("web_crawl") or {}).get("sources") or []
        songs = web_trends.get("songs") or []
        formats = web_trends.get("reel_formats") or []
        hashtags = web_trends.get("hashtags") or []
        topics = web_trends.get("topics") or []
        google_trends = web_trends.get("google_trends") or []

        lines = [
            "Instagram trends today (aggregated from web sources + Google Trends).",
            f"Scanned {len(sources)} sources including SocialBee, Metricool, Google Trends, and more.",
        ]
        if formats:
            names = ", ".join(item.get("name") for item in formats[:4] if item.get("name"))
            lines.append(f"Trending Reel formats: {names}.")
        if songs:
            song_labels = ", ".join(item.get("label") or item.get("title") for item in songs[:3])
            lines.append(f"Trending songs/audio: {song_labels}.")
        if hashtags:
            tags = ", ".join(f"#{item.get('hashtag') or item.get('tag')}" for item in hashtags[:5])
            lines.append(f"Popular hashtags: {tags}.")
        if google_trends:
            rising = ", ".join(
                item.get("topic") or item.get("key")
                for item in google_trends[:5]
                if item.get("topic") or item.get("key")
            )
            lines.append(f"Google Trends rising searches: {rising}.")
        if topics:
            topic_names = ", ".join(item.get("topic") or item.get("key") for item in topics[:3])
            lines.append(f"Cultural topics: {topic_names}.")
        if not formats and not songs and not hashtags:
            lines.append("Limited trend signals extracted; check source connectivity.")
        state["trend_summary"] = " ".join(lines)
        return state

    company = config.get("company") or {}
    company_name = company.get("name") or config.get("company_name") or "the company"
    detected_category = config.get("detected_category") or config.get("category")
    region = config.get("region") or (config.get("filters") or {}).get("region") or "target region"
    discovery_source = config.get("discovery_source") or "instagram_search"
    discovery_label = DISCOVERY_LABELS.get(discovery_source, discovery_source)

    top_trends = (state.get("trend_scores") or [])[:5]
    top_hashtags = [item for item in top_trends if item.get("group_type") == "hashtag"][:3]
    top_topics = [item for item in top_trends if item.get("group_type") == "topic"][:3]
    top_formats = [item for item in top_trends if item.get("group_type") == "reel_format"][:3]
    viral_count = len(state.get("viral_posts") or [])
    post_count = len(state.get("processed_posts") or [])
    competitor_count = len(state.get("discovered_influencers") or [])
    content_mix = state.get("content_mix") or []
    web_songs = web_trends.get("songs") or []

    lines = [
        f"Instagram trend analysis for {company_name} ({detected_category or 'industry'}) in {region}.",
        f"Analyzed {competitor_count} account(s) via {discovery_label}.",
        f"Processed {post_count} posts; flagged {viral_count} viral posts.",
    ]

    if top_hashtags:
        tags = ", ".join(f"#{item['key']}" for item in top_hashtags)
        lines.append(f"Trending hashtags: {tags}.")
    if top_formats:
        formats = ", ".join(item["key"] for item in top_formats)
        lines.append(f"Trending Reel formats in your niche: {formats}.")
    elif top_topics:
        topics = ", ".join(item["key"] for item in top_topics)
        lines.append(f"Trending topics: {topics}.")
    if web_songs:
        lines.append(
            "Trending audio this week: "
            + ", ".join(item.get("label") or item.get("title") for item in web_songs[:2])
            + "."
        )

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
