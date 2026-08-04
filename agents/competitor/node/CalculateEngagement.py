from agents.competitor.state.competitor_state import CompetitorState


async def CalculateEngagementNode(state: CompetitorState) -> CompetitorState:
    metrics: list[dict] = []
    for post in state.get("processed_posts") or []:
        followers = max(int(post.get("followers") or 0), 1)
        likes = int(post.get("likes") or 0)
        comments = int(post.get("comments") or 0)
        views = int(post.get("views") or 0)
        interactions = likes + comments
        engagement_rate = round((interactions / followers) * 100, 4)
        metrics.append(
            {
                "media_id": post.get("media_id"),
                "username": post.get("username"),
                "likes": likes,
                "comments": comments,
                "views": views,
                "followers": followers,
                "interactions": interactions,
                "engagement_rate": engagement_rate,
            }
        )
        post["engagement_rate"] = engagement_rate
        post["interactions"] = interactions

    state["engagement_metrics"] = metrics
    state["processed_posts"] = state.get("processed_posts") or []
    return state
