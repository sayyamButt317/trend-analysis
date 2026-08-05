"""Shared filters to reject listicles / directories — industry-agnostic for multi-tenant SaaS."""

from __future__ import annotations

import re

# Title patterns that almost never are a real company name (any industry).
_LISTICLE_NAME_RE = re.compile(
    r"("
    r"\btop\s+\d*"
    r"|\btop\s+[\w&/+\- ]{0,40}\bcompanies\b"
    r"|\bbest\s+[\w&/+\- ]{0,40}\bcompanies\b"
    r"|\bcompanies\s+in\b"
    r"|\bdominating\b"
    r"|\brevealed\b"
    r"|\blist\s+of\b"
    r"|\branking\b"
    r"|\bdirectory\b"
    r"|\bagency\s+list"
    r"|\bmanifest\b"
    r"|\bclutch\b"
    r"|\btechbehemoths\b"
    r"|\bgoodfirms\b"
    r"|\bdesignrush\b"
    r"|\bsortlist\b"
    r"|\bpeoplepakistan\b"
    r")",
    re.I,
)

# Directory / aggregator brands only — never hard-block real companies by industry.
_BLOCKED_NAME_TOKENS = (
    "companies in",
    "dominating",
    "revealed",
    "list of",
    "ranking",
    "peoplepakistan",
    "techbehemoths",
    "the manifest",
    "goodfirms",
    "designrush",
    "sortlist",
    "clutch.co",
)

_BLOCKED_HOST_OR_PATH = (
    "techbehemoths.com",
    "themanifest.com",
    "clutch.co",
    "goodfirms.co",
    "designrush.com",
    "sortlist.com",
    "peoplepakistan",
    "/top-",
    "/best-",
    "/companies-in-",
    "list-of-",
    "-companies-in-",
    "/ai-development-companies",
)


def is_blocked_competitor_name(name: str | None) -> bool:
    """True if the name looks like a listicle or directory, not a real company."""
    text = (name or "").strip()
    if len(text) < 2:
        return True
    lowered = text.lower()
    if any(token in lowered for token in _BLOCKED_NAME_TOKENS):
        return True
    if _LISTICLE_NAME_RE.search(text):
        return True
    # Real company names are rarely this long and full of year/marketing fluff.
    if len(text) > 80 and any(ch.isdigit() for ch in text):
        return True
    return False


def is_blocked_competitor_url(url: str | None) -> bool:
    text = (url or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in _BLOCKED_HOST_OR_PATH)


def is_junk_competitor(item: dict) -> bool:
    """Reject listicle / directory candidates before they enter the pipeline."""
    name = item.get("name") or item.get("title") or ""
    if is_blocked_competitor_name(str(name)):
        return True
    website = item.get("website") or item.get("url") or ""
    if is_blocked_competitor_url(str(website)):
        return True
    linkedin = item.get("linkedin_url") or (item.get("socials") or {}).get("linkedin") or ""
    if linkedin:
        lowered_li = str(linkedin).lower()
        if "linkedin.com" in lowered_li and "/company/" not in lowered_li:
            return True
    return False
