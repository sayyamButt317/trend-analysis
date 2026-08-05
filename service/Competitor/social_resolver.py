import logging
import re
from typing import Any
from agents.trend.services.company_social_analyzer import resolve_company_social_handles
from service.Competitor.platforms import filter_competitor_socials

logger = logging.getLogger(__name__)


class SocialResolverService:
    async def resolve_for_company(
        self,
        *,
        name: str,
        website: str | None = None,
        region: str | None = None,
        description: str | None = None,
        social_links: dict[str, str] | None = None,
        resolve_linkedin: bool = False,
    ) -> dict[str, str | None]:
        links = filter_competitor_socials(social_links)
        company_payload = {
            "name": name,
            "website": website,
            "profile": description or "",
            "instagram_url": links.get("instagram"),
            "linkedin_url": links.get("linkedin"),
        }
        handles = await resolve_company_social_handles(
            company_payload,
            region=region,
            resolve_linkedin=resolve_linkedin,
        )
        return {
            "instagram": handles.get("instagram_username") or _handle_from_url(links.get("instagram")),
            "linkedin": handles.get("linkedin_url") or links.get("linkedin"),
        }

    async def resolve_batch(
        self,
        candidates: list[dict[str, Any]],
        *,
        region: str | None = None,
        resolve_linkedin: bool = False,
        stop_when_instagram_count: int | None = None,
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        instagram_found = 0
        for candidate in candidates:
            social_links = filter_competitor_socials(candidate.get("social_links"))
            existing_ig = _handle_from_url(social_links.get("instagram"))
            if existing_ig:
                instagram_found += 1
                enriched.append(
                    {
                        **candidate,
                        "social_links": social_links,
                        "socials": {"instagram": existing_ig, "linkedin": social_links.get("linkedin")},
                    }
                )
                if stop_when_instagram_count and instagram_found >= stop_when_instagram_count:
                    break
                continue

            socials = await self.resolve_for_company(
                name=candidate.get("name") or candidate.get("company_name") or "",
                website=candidate.get("website"),
                region=region,
                description=candidate.get("description"),
                social_links=social_links,
                resolve_linkedin=resolve_linkedin,
            )
            enriched.append(
                {
                    **candidate,
                    "social_links": social_links,
                    "socials": socials,
                }
            )
            if socials.get("instagram"):
                instagram_found += 1
                if stop_when_instagram_count and instagram_found >= stop_when_instagram_count:
                    break
        return enriched


def _handle_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"instagram\.com/([A-Za-z0-9._]+)", url, re.I)
    return match.group(1).lower() if match else None
