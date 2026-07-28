import logging
from agents.trend.Nodes.common import HASHTAG_RE, MENTION_RE
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


def _first_int(post: dict, *keys: str) -> int:
    for key in keys:
        if key in post and post[key] is not None:
            try:
                return int(post[key])
            except (TypeError, ValueError):
                logger.warning(
                    "Non-numeric value for key=%s value=%r on post id=%s",
                    key, post[key], post.get("id"),
                )
                return 0
    return 0


async def ExtractPostDataNode(state: TrendState) -> TrendState:
    if state.get("error"):
        state["processed_posts"] = []
        return state

    raw_posts = state.get("raw_posts") or []
    processed: list[dict] = []
    skipped = 0

    for post in raw_posts:
        try:
            caption = post.get("caption") or ""
            processed.append(
                {
                    **post,
                    "caption": caption,
                    "hashtags": [h.lower() for h in HASHTAG_RE.findall(caption)],
                    "mentions": [m.lower() for m in MENTION_RE.findall(caption)],
                    # Support both Graph API field names and any aliased/legacy names.
                    "likes": _first_int(post, "likes", "like_count"),
                    "comments": _first_int(post, "comments", "comments_count"),
                    "views": _first_int(post, "views", "view_count", "play_count"),
                    "followers": _first_int(post, "followers", "followers_count"),
                }
            )
        except Exception:
            skipped += 1
            logger.exception("Failed to process post id=%s, skipping", post.get("id"))
            continue

    if skipped:
        logger.warning("Skipped %s malformed post(s) out of %s", skipped, len(raw_posts))

    logger.info("Processed %s post(s) into processed_posts", len(processed))
    state["processed_posts"] = processed
    return state