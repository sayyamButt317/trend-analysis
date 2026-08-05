import logging
from typing import Any
from models.company import CompanyProfile
from service.Competitor.competitor_ranker import CompetitorRanker

logger = logging.getLogger(__name__)

EXCLUDED_NAME_TERMS = frozenset(
    {
        "wikipedia",
        "linkedin",
        "indeed",
        "glassdoor",
        "news",
        "blog",
        "jobs",
        "course",
    }
)


class CompanyVerifier:
    def __init__(self) -> None:
        self.ranker = CompetitorRanker()

    def verify(
        self,
        *,
        company: CompanyProfile,
        candidates: list[dict[str, Any]],
        region: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        verified: list[dict[str, Any]] = []
        min_score = 0.28
        for candidate in candidates:
            name = (candidate.get("name") or "").lower()
            if not name or any(term in name for term in EXCLUDED_NAME_TERMS):
                continue
            socials = candidate.get("socials") or {}
            has_presence = bool(
                candidate.get("website")
                or socials.get("instagram")
                or socials.get("linkedin")
            )
            if not has_presence:
                continue
            score = self.ranker.score_candidate(company, candidate, region=region)
            if score.get("overall", 0) < min_score:
                continue
            username = socials.get("instagram") or (candidate.get("social_links") or {}).get("instagram")
            if isinstance(username, str) and "instagram.com" in username:
                from service.Competitor.social_resolver import _handle_from_url
                username = _handle_from_url(username)
            verified.append(
                {
                    **candidate,
                    "similarity": score,
                    "match_score": score.get("overall"),
                    "match_reasons": [score.get("explanation") or "Verified competitor match"],
                    "authenticity": "verified",
                    "region_match": score.get("geography", 0) >= 0.5,
                    "niche_match": score.get("industry", 0) >= 0.35 or score.get("services", 0) >= 0.25,
                    "username": username,
                }
            )
        verified.sort(key=lambda item: float(item.get("match_score") or 0), reverse=True)
        return verified[:limit]
