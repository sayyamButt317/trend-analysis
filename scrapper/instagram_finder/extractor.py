import re

from scrapper.instagram_finder.constants import RESERVED_INSTAGRAM_PATHS
INSTAGRAM_PROFILE_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?",
    re.IGNORECASE,
)

INSTAGRAM_URL_BLOCKLIST = (
    "/p/",
    "/reel/",
    "/reels/",
    "/tv/",
    "/explore/",
    "/popular/",
    "/stories/",
)


def extract_username(url: str) -> str | None:
    if not url:
        return None

    if any(blocked in url for blocked in INSTAGRAM_URL_BLOCKLIST):
        return None

    match = INSTAGRAM_PROFILE_PATTERN.search(url.strip())
    if not match:
        return None

    username = match.group(1).strip().lstrip("@")
    if not username or username.lower() in RESERVED_INSTAGRAM_PATHS:
        return None

    return username
