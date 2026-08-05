"""Shared helpers for competitor discovery nodes."""

from __future__ import annotations

from typing import Any


def manual_competitor_inputs(config: dict[str, Any] | None) -> list[str]:
    """Return user-provided competitor strings from agent config/filters."""
    config = config or {}
    filters = config.get("filters") if isinstance(config.get("filters"), dict) else {}
    values = (
        filters.get("competitors")
        or config.get("competitors")
        or []
    )
    if not isinstance(values, list):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


def has_manual_competitors(config: dict[str, Any] | None) -> bool:
    return bool(manual_competitor_inputs(config))
