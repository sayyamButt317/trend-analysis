from collections import defaultdict

from agents.trend.state.trend_state import TrendState


def _is_reel(post: dict) -> bool:
    product_type = (post.get("media_product_type") or "").upper()
    media_type = (post.get("media_type") or "").upper()
    return product_type == "REELS" or media_type in {"VIDEO", "REEL"}


async def ExtractAudioNode(state: TrendState) -> TrendState:
    audio_groups: dict[str, dict] = defaultdict(
        lambda: {
            "audio_type": "",
            "reel_count": 0,
            "creators": set(),
            "total_views": 0,
            "total_engagement_rate": 0.0,
        }
    )
    audios: list[dict] = []

    for post in state.get("processed_posts") or []:
        if not _is_reel(post):
            continue

        audio_type = (post.get("media_audio_type") or "UNKNOWN").upper()
        group = audio_groups[audio_type]
        group["audio_type"] = audio_type
        group["reel_count"] += 1
        group["creators"].add(post.get("username") or "")
        group["total_views"] += int(post.get("views") or 0)
        group["total_engagement_rate"] += float(post.get("engagement_rate") or 0)

        audios.append(
            {
                "media_id": post.get("media_id"),
                "username": post.get("username"),
                "audio_type": audio_type,
                "views": int(post.get("views") or 0),
                "engagement_rate": float(post.get("engagement_rate") or 0),
                "permalink": post.get("permalink"),
            }
        )

    state["audios"] = audios
    state["audio_summary"] = [
        {
            "audio_type": audio_type,
            "label": "Licensed Music" if audio_type == "MUSIC" else "Original Sound",
            "reel_count": entry["reel_count"],
            "creator_count": len(entry["creators"]),
            "total_views": entry["total_views"],
            "avg_engagement_rate": round(
                entry["total_engagement_rate"] / max(entry["reel_count"], 1),
                4,
            ),
        }
        for audio_type, entry in sorted(
            audio_groups.items(),
            key=lambda item: item[1]["total_views"],
            reverse=True,
        )
    ]
    return state
