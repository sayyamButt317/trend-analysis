import re
from typing import Any


NOISE_BIO_TERMS = frozenset(
    {
        "fitness",
        "fashion",
        "beauty",
        "makeup",
        "food blogger",
        "travel blogger",
        "influencer",
        "model",
        "personal trainer",
        "recipe",
        "ootd",
    }
)

IT_BIO_TERMS = frozenset(
    {
        "software",
        "development",
        "developer",
        "devops",
        "ai",
        "ml",
        "technology",
        "tech",
        "digital",
        "agency",
        "consulting",
        "it services",
        "app development",
        "web development",
        "staff augmentation",
        "outsourcing",
        "saas",
        "cloud",
        "engineering",
        "automation",
    }
)

REGION_TERMS = {
    "gcc": ("gcc", "gulf", "uae", "dubai", "saudi", "riyadh", "qatar", "kuwait", "bahrain", "oman"),
    "mena": ("mena", "middle east", "gcc", "uae", "saudi", "egypt", "dubai"),
    "north america": ("usa", "us", "united states", "canada", "north america", "america"),
    "europe": ("europe", "uk", "united kingdom", "germany", "france"),
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 2}


def _phrase_hits(text: str, phrases: list[str]) -> list[str]:
    lowered = (text or "").lower()
    hits: list[str] = []
    for phrase in phrases:
        if phrase.lower() in lowered:
            hits.append(phrase)
    return hits


def _region_hits(bio: str, region: str | None) -> list[str]:
    if not region:
        return []
    key = region.lower()
    terms = REGION_TERMS.get(key, (key,))
    return _phrase_hits(bio, list(terms))


def score_competitor_match(
    *,
    profile: dict[str, Any] | None,
    candidate: dict[str, Any],
    target_keywords: list[str],
    company_signals: dict[str, Any] | None = None,
    region: str | None = None,
) -> tuple[float, list[str]]:
    bio = (profile or {}).get("biography") or candidate.get("bio") or ""
    name = (profile or {}).get("name") or candidate.get("name") or ""
    website = (profile or {}).get("website") or candidate.get("website") or ""
    followers = int((profile or {}).get("followers_count") or candidate.get("followers") or 0)
    text = f"{name} {bio} {website}".lower()
    tokens = _tokenize(text)

    reasons: list[str] = []
    score = 0.0

    signals = company_signals or {}
    keywords = list(
        dict.fromkeys(
            [
                *(target_keywords or []),
                *(signals.get("flagship_services") or []),
                *(signals.get("services") or [])[:8],
                *(signals.get("technologies") or [])[:5],
            ]
        )
    )

    keyword_hits = _phrase_hits(text, keywords)
    if keyword_hits:
        kw_score = min(len(keyword_hits) * 0.12, 0.45)
        score += kw_score
        reasons.append(f"Service/tech overlap: {', '.join(keyword_hits[:4])}")

    it_hits = [term for term in IT_BIO_TERMS if term in text]
    if it_hits:
        score += min(len(it_hits) * 0.05, 0.2)
        reasons.append(f"IT/tech profile signals: {', '.join(it_hits[:4])}")

    region_hits = _region_hits(bio, region)
    if region_hits:
        score += 0.12
        reasons.append(f"Region mention: {', '.join(region_hits[:3])}")

    source = candidate.get("source") or ""
    if source == "web_company":
        score += 0.08
        reasons.append("Found via business web search")
    elif source == "llm_query":
        score += 0.06
        reasons.append("Matched LLM competitor query")

    if website:
        score += 0.05
        reasons.append("Has business website on profile")

    if followers >= 500:
        score += 0.05
    if followers >= 2000:
        score += 0.05

    noise_hits = [term for term in NOISE_BIO_TERMS if term in text]
    if noise_hits and not it_hits:
        score -= 0.35
        reasons.append(f"Likely non-business account: {', '.join(noise_hits[:3])}")

    if not bio and not name:
        score -= 0.15
        reasons.append("Sparse profile data")

    discovery_query = candidate.get("discovered_by") or ""
    if discovery_query and any(k.lower() in discovery_query.lower() for k in keywords[:5]):
        score += 0.05

    score = round(max(0.0, min(score, 1.0)), 3)
    if score >= 0.65:
        reasons.insert(0, "Strong competitor match")
    elif score >= 0.4:
        reasons.insert(0, "Moderate competitor match")
    else:
        reasons.insert(0, "Weak competitor match")

    return score, reasons


def rank_competitors(
    candidates: list[dict],
    *,
    profiles_by_username: dict[str, dict],
    target_keywords: list[str],
    company_signals: dict[str, Any] | None,
    region: str | None,
    min_match_score: float = 0.25,
    limit: int = 10,
) -> list[dict]:
    ranked: list[dict] = []
    for candidate in candidates:
        username = candidate.get("username")
        if not username:
            continue
        profile = profiles_by_username.get(username)
        score, reasons = score_competitor_match(
            profile=profile,
            candidate=candidate,
            target_keywords=target_keywords,
            company_signals=company_signals,
            region=region,
        )
        if score < min_match_score:
            continue
        enriched = {
            **candidate,
            "match_score": score,
            "match_reasons": reasons,
            "name": (profile or {}).get("name") or candidate.get("name"),
            "bio": (profile or {}).get("biography") or candidate.get("bio"),
            "followers": int((profile or {}).get("followers_count") or candidate.get("followers") or 0),
            "website": (profile or {}).get("website") or candidate.get("website"),
            "profile_picture_url": (profile or {}).get("profile_picture_url"),
        }
        ranked.append(enriched)

    ranked.sort(
        key=lambda item: (
            float(item.get("match_score") or 0),
            int(item.get("followers") or 0),
        ),
        reverse=True,
    )
    return ranked[:limit]

