import re

from scrapper.instagram_finder.constants import RESERVED_INSTAGRAM_PATHS

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def is_valid_instagram_username(username: str) -> bool:
    handle = (username or "").strip().lstrip("@")
    if not handle:
        return False
    if handle.lower() in RESERVED_INSTAGRAM_PATHS:
        return False
    if handle.endswith("."):
        return False
    if ".." in handle:
        return False
    return bool(USERNAME_PATTERN.match(handle))
