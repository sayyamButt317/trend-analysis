"""Shared filters for meaningful service/theme gap labels."""

from __future__ import annotations

import re
from typing import Any

_JUNK_GAP_RE = re.compile(
    r"^("
    r"[#@$%&*+=~^|<>{}[\]()\"'`\\/_.,;:!?\-]+|"
    r"\(?[\d,.]+(\+)?(k|m|b)?\)?|"
    r"\$[\d,.]+(\+)?|"
    r"\(?\s*(lahore|karachi|islamabad|pakistan|pk)\s*\)?"
    r")$",
    re.I,
)
_STOP_GAP_TERMS = {
    "and", "the", "for", "with", "from", "your", "our", "their", "this", "that",
    "are", "was", "were", "have", "has", "been", "will", "can", "all", "any",
    "company", "companies", "services", "service", "solutions", "solution",
    "best", "top", "more", "most", "also", "into", "over", "under", "about",
}


def is_meaningful_gap_term(value: Any) -> bool:
    text = str(value or "").strip()
    if len(text) < 3:
        return text.lower() in {"ai", "ml", "qa", "ui", "ux", "seo", "api"}
    if _JUNK_GAP_RE.match(text):
        return False
    lowered = text.lower()
    if lowered in _STOP_GAP_TERMS:
        return False
    if text.count("#") >= 1 and len(text) <= 4:
        return False
    if re.fullmatch(r"[\W\d_]+", text):
        return False
    alpha = sum(1 for ch in text if ch.isalpha())
    if alpha < 2:
        return False
    return True


def clean_gap_terms(values: list[Any] | None, *, limit: int = 12) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        label = raw if isinstance(raw, str) else (
            (raw or {}).get("item")
            or (raw or {}).get("service")
            or (raw or {}).get("technology")
            or (raw or {}).get("theme")
            or ""
        )
        text = re.sub(r"\s+", " ", str(label or "").strip(" ,.-"))
        key = text.lower()
        if not text or key in seen or not is_meaningful_gap_term(text):
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned
