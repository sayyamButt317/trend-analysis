from datetime import datetime, timedelta, timezone

from agents.trend.Nodes.common import parse_timestamp
from agents.trend.state.trend_state import TrendState


async def DetectViralityNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    min_engagement_rate = float(config.get("min_engagement_rate") or 1.0)
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=7)

    viral_posts: list[dict] = []
    for post in state.get("processed_posts") or []:
        engagement_rate = float(post.get("engagement_rate") or 0)
        views = int(post.get("views") or 0)
        interactions = int(post.get("interactions") or 0)
        timestamp = parse_timestamp(post.get("timestamp"))
        is_recent = bool(timestamp and timestamp >= recent_cutoff)
        is_reel = (post.get("media_product_type") or "").upper() == "REELS" or (
            post.get("media_type") or ""
        ).upper() in {"VIDEO", "REEL"}

        view_rate = round((interactions / views) * 100, 4) if views > 0 else 0.0
        is_viral = engagement_rate >= min_engagement_rate or (
            is_recent and interactions >= 100
        ) or (is_reel and views >= 10000 and view_rate >= 2.0)

        if is_viral:
            viral_posts.append(
                {
                    **post,
                    "is_recent": is_recent,
                    "is_reel": is_reel,
                    "view_rate": view_rate,
                    "view_velocity": views,
                    "engagement_velocity": interactions,
                    "growth_rate": engagement_rate,
                }
            )

    viral_posts.sort(
        key=lambda item: (
            float(item.get("engagement_rate") or 0),
            int(item.get("views") or 0),
            int(item.get("interactions") or 0),
        ),
        reverse=True,
    )
    state["viral_posts"] = viral_posts
    return state
