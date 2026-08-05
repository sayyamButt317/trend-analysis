import re
from typing import Any


DEFAULT_COMPETITOR_TARGET = 10
MIN_AUTHENTIC_MATCH_SCORE = 0.38

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

REGION_TERMS: dict[str, tuple[str, ...]] = {
    "gcc": ("gcc", "gulf", "uae", "dubai", "saudi", "riyadh", "qatar", "kuwait", "bahrain", "oman"),
    "mena": ("mena", "middle east", "gcc", "uae", "saudi", "egypt", "dubai"),
    "north america": ("usa", "us", "united states", "canada", "north america", "america"),
    "europe": ("europe", "uk", "united kingdom", "germany", "france"),
    "uae": ("uae", "dubai", "abu dhabi", "sharjah", "united arab emirates", "emirates"),
    "united arab emirates": ("uae", "dubai", "abu dhabi", "sharjah", "united arab emirates", "emirates"),
    "dubai": ("dubai", "uae", "abu dhabi", "united arab emirates"),
    "saudi arabia": ("saudi", "riyadh", "jeddah", "ksa", "saudi arabia"),
    "sa": ("saudi", "riyadh", "jeddah", "ksa"),
    "pakistan": ("pakistan", "lahore", "karachi", "islamabad", "rawalpindi", "faisalabad", "software house", "pk"),
    "pk": ("pakistan", "lahore", "karachi", "islamabad", "software house"),
    "india": ("india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune"),
    "uk": ("uk", "united kingdom", "london", "england", "scotland"),
    "united kingdom": ("uk", "united kingdom", "london", "england"),
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 2}


def _phrase_hits(text: str, phrases: list[str]) -> list[str]:
    lowered = (text or "").lower()
    hits: list[str] = []
    for phrase in phrases:
        if phrase and phrase.lower() in lowered:
            hits.append(phrase)
    return hits


def _region_terms(region: str | None) -> tuple[str, ...]:
    if not region:
        return ()
    key = region.lower().strip()
    if key in REGION_TERMS:
        return REGION_TERMS[key]
    for map_key, terms in REGION_TERMS.items():
        if map_key in key or key in map_key:
            return terms
    return (key,)


def _region_hits(text: str, region: str | None) -> list[str]:
    if not region:
        return []
    return _phrase_hits(text, list(_region_terms(region)))


def competitor_profile_text(
    profile: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> str:
    bio = (profile or {}).get("biography") or candidate.get("bio") or ""
    name = (profile or {}).get("name") or candidate.get("name") or ""
    website = (profile or {}).get("website") or candidate.get("website") or ""
    discovered_by = candidate.get("discovered_by") or ""
    return f"{name} {bio} {website} {discovered_by}"


def has_region_match(text: str, region: str | None) -> bool:
    if not region:
        return True
    return bool(_region_hits(text, region))


def _niche_keywords(
    target_keywords: list[str] | None,
    company_signals: dict[str, Any] | None,
) -> list[str]:
    signals = company_signals or {}
    return list(
        dict.fromkeys(
            [
                *(target_keywords or []),
                *(signals.get("flagship_services") or []),
                *(signals.get("services") or [])[:10],
                *(signals.get("technologies") or [])[:6],
                *(signals.get("keywords") or [])[:12],
            ]
        )
    )


def has_niche_match(
    text: str,
    *,
    target_keywords: list[str] | None,
    company_signals: dict[str, Any] | None,
) -> bool:
    keywords = _niche_keywords(target_keywords, company_signals)
    if _phrase_hits(text, keywords):
        return True

    lowered = (text or "").lower()
    it_hits = [term for term in IT_BIO_TERMS if term in lowered]
    noise_hits = [term for term in NOISE_BIO_TERMS if term in lowered]
    if it_hits and not (noise_hits and len(it_hits) < 2):
        return True
    return False


def score_competitor_match(
    *,
    profile: dict[str, Any] | None,
    candidate: dict[str, Any],
    target_keywords: list[str],
    company_signals: dict[str, Any] | None = None,
    region: str | None = None,
) -> tuple[float, list[str]]:
    text = competitor_profile_text(profile, candidate).lower()
    bio = (profile or {}).get("biography") or candidate.get("bio") or ""
    name = (profile or {}).get("name") or candidate.get("name") or ""
    website = (profile or {}).get("website") or candidate.get("website") or ""
    display_text = f"{name} {bio} {website}".lower()
    followers = int((profile or {}).get("followers_count") or candidate.get("followers") or 0)

    reasons: list[str] = []
    score = 0.0

    signals = company_signals or {}
    keywords = _niche_keywords(target_keywords, signals)

    keyword_hits = _phrase_hits(display_text, keywords)
    if keyword_hits:
        kw_score = min(len(keyword_hits) * 0.12, 0.45)
        score += kw_score
        reasons.append(f"Niche/service overlap: {', '.join(keyword_hits[:4])}")

    it_hits = [term for term in IT_BIO_TERMS if term in display_text]
    if it_hits:
        score += min(len(it_hits) * 0.05, 0.2)
        reasons.append(f"IT/tech profile signals: {', '.join(it_hits[:4])}")

    region_hits = _region_hits(display_text, region)
    if region_hits:
        score += 0.18
        reasons.append(f"Region match: {', '.join(region_hits[:3])}")
    elif region:
        score -= 0.35
        reasons.append(f"No region signal for {region}")

    if not has_niche_match(display_text, target_keywords=keywords, company_signals=signals):
        score -= 0.25
        reasons.append("Weak niche alignment with company services")

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

    noise_hits = [term for term in NOISE_BIO_TERMS if term in display_text]
    if noise_hits and not it_hits:
        score -= 0.45
        reasons.append(f"Likely non-business account: {', '.join(noise_hits[:3])}")

    if not bio and not name:
        score -= 0.15
        reasons.append("Sparse profile data")

    discovery_query = candidate.get("discovered_by") or ""
    if discovery_query and any(k.lower() in discovery_query.lower() for k in keywords[:5]):
        score += 0.05

    score = round(max(0.0, min(score, 1.0)), 3)
    if score >= 0.65:
        reasons.insert(0, "Strong authentic competitor match")
    elif score >= 0.4:
        reasons.insert(0, "Moderate authentic competitor match")
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
            "region_match": has_region_match(competitor_profile_text(profile, candidate), region),
            "niche_match": has_niche_match(
                competitor_profile_text(profile, candidate),
                target_keywords=target_keywords,
                company_signals=company_signals,
            ),
        }
        ranked.append(enriched)

    ranked.sort(
        key=lambda item: (
            bool(item.get("region_match")),
            bool(item.get("niche_match")),
            float(item.get("match_score") or 0),
            int(item.get("followers") or 0),
        ),
        reverse=True,
    )
    return ranked[:limit]


def filter_authentic_competitors(
    candidates: list[dict],
    *,
    profiles_by_username: dict[str, dict],
    target_keywords: list[str],
    company_signals: dict[str, Any] | None,
    region: str | None,
    limit: int = DEFAULT_COMPETITOR_TARGET,
    min_match_score: float = MIN_AUTHENTIC_MATCH_SCORE,
    require_region: bool = True,
    require_niche: bool = True,
) -> list[dict]:
    """Keep only region + niche aligned competitors up to the target count."""
    scored = rank_competitors(
        candidates,
        profiles_by_username=profiles_by_username,
        target_keywords=target_keywords,
        company_signals=company_signals,
        region=region,
        min_match_score=0.2,
        limit=len(candidates),
    )

    authentic: list[dict] = []
    for item in scored:
        profile = profiles_by_username.get(item.get("username") or "")
        text = competitor_profile_text(profile, item)

        if require_region and region and not has_region_match(text, region):
            continue
        if require_niche and not has_niche_match(
            text,
            target_keywords=target_keywords,
            company_signals=company_signals,
        ):
            continue
        if float(item.get("match_score") or 0) < min_match_score:
            continue

        authentic.append(
            {
                **item,
                "region_match": True,
                "niche_match": True,
                "authenticity": "verified",
            }
        )
        if len(authentic) >= limit:
            break

    return authentic
