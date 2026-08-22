import re
from playwright.async_api import Page

def LabelMatchesProfile(label: str, profile_name: str) -> bool:
    """True if invite label is for this profile (or plain Connect CTA)."""
    text = (label or "").strip()
    if not text:
        return False
    if re.search(r"connections", text, re.I):
        return False
    name = (profile_name or "").strip()
    if not name:
        # Without a name, allow Invite…connect or plain Connect (caller must top-rank)
        if re.search(r"invite", text, re.I) and re.search(r"connect", text, re.I):
            return True
        return bool(re.search(r"^\s*\+?\s*connect\s*$", text, re.I))
    if re.search(r"invite", text, re.I) and re.search(r"connect", text, re.I):
        tokens = [t for t in re.split(r"\s+", name) if len(t) > 1]
        if tokens and all(re.search(re.escape(t), text, re.I) for t in tokens):
            return True
        return False
    return bool(re.search(r"^\s*\+?\s*connect\s*$", text, re.I))
