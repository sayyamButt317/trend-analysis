from agents.trend.state.trend_state import TrendState

DISCOVERY_LABELS = {
    "instagram_search": "Instagram live search",
    "seed_usernames": "provided usernames",
    "database": "database",
}


async def GenerateTrendSummaryNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    country = config.get("country") or "all regions"
    category = config.get("category")
    platform = config.get("platform") or "instagram"
    discovery_source = config.get("discovery_source") or "instagram_search"
    discovery_label = DISCOVERY_LABELS.get(discovery_source, discovery_source)

    top_trends = (state.get("trend_scores") or [])[:5]
    top_hashtags = [
        item for item in top_trends if item.get("group_type") == "hashtag"
    ][:3]
    top_topics = [item for item in top_trends if item.get("group_type") == "topic"][:3]
    viral_count = len(state.get("viral_posts") or [])
    post_count = len(state.get("processed_posts") or [])
    influencer_count = len(state.get("discovered_influencers") or [])
    viral_categories = (state.get("viral_categories") or [])[:3]
    viral_sounds = (state.get("viral_sounds") or [])[:2]

    lines = [
        f"Instagram trend scan for {country} ({platform}).",
    ]
    if category:
        lines.append(f"Category filter: {category}.")
    lines.extend(
        [
            f"Discovered {influencer_count} influencer(s) via {discovery_label}.",
            f"Analyzed {post_count} posts; flagged {viral_count} viral posts.",
        ]
    )
    if top_hashtags:
        tags = ", ".join(f"#{item['key']}" for item in top_hashtags)
        lines.append(f"Top hashtags: {tags}.")
    if viral_categories:
        categories = ", ".join(item["category"] for item in viral_categories)
        lines.append(f"Viral categories: {categories}.")
    elif top_topics:
        topics = ", ".join(item["key"] for item in top_topics)
        lines.append(f"Top topics: {topics}.")
    if viral_sounds:
        sounds = ", ".join(
            f"{item['label']} ({item['viral_reel_count']} reels)"
            for item in viral_sounds
        )
        lines.append(f"Viral sounds: {sounds}.")
    if not top_hashtags and not top_topics and not viral_categories:
        lines.append("No strong hashtag or topic clusters detected in this run.")

    state["trend_summary"] = " ".join(lines)
    return state
