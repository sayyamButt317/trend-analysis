"""Social platforms used in competitor analysis (Instagram + LinkedIn only)."""

from __future__ import annotations

from typing import Any

COMPETITOR_SOCIAL_PLATFORMS = frozenset({"instagram", "linkedin"})


def filter_competitor_socials(socials: dict[str, Any] | None) -> dict[str, str]:
    if not socials:
        return {}
    return {
        key: str(value)
        for key, value in socials.items()
        if key in COMPETITOR_SOCIAL_PLATFORMS and value
    }
