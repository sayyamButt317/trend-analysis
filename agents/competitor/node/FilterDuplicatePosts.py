from agents.trend.state.trend_state import TrendState


async def FilterDuplicatePostsNode(state: TrendState) -> TrendState:
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    unique_posts: list[dict] = []

    for post in state.get("processed_posts") or []:
        media_id = str(post.get("media_id") or "")
        permalink = str(post.get("permalink") or "")
        media_url = str(post.get("media_url") or "")

        if media_id and media_id in seen_ids:
            continue
        url_key = permalink or media_url
        if url_key and url_key in seen_urls:
            continue

        if media_id:
            seen_ids.add(media_id)
        if url_key:
            seen_urls.add(url_key)
        unique_posts.append(post)

    state["processed_posts"] = unique_posts
    return state
