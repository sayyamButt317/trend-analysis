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
        for candidate in candidates:
            name = (candidate.get("name") or "").lower()
            if not name or any(term in name for term in EXCLUDED_NAME_TERMS):
                continue
            if not candidate.get("website") and not (candidate.get("socials") or {}).get("instagram"):
                continue
            score = self.ranker.score_candidate(company, candidate, region=region)
            if score.get("overall", 0) < 0.35:
                continue
            verified.append(
                {
                    **candidate,
                    "similarity": score,
                    "match_score": score.get("overall"),
                    "match_reasons": [score.get("explanation") or "Verified competitor match"],
                    "authenticity": "verified",
                    "region_match": score.get("geography", 0) >= 0.5,
                    "niche_match": score.get("industry", 0) >= 0.5,
                    "username": (candidate.get("socials") or {}).get("instagram"),
                }
            )
        verified.sort(key=lambda item: float(item.get("match_score") or 0), reverse=True)
        return verified[:limit]
