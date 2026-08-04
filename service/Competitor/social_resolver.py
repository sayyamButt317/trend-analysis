import logging
import re
from typing import Any

from agents.trend.services.company_social_analyzer import resolve_company_social_handles

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
    ) -> dict[str, str | None]:
        company_payload = {
            "name": name,
            "website": website,
            "profile": description or "",
            "instagram_url": (social_links or {}).get("instagram"),
            "linkedin_url": (social_links or {}).get("linkedin"),
        }
        handles = await resolve_company_social_handles(company_payload, region=region)
        resolved = {
            "instagram": handles.get("instagram_username") or _handle_from_url((social_links or {}).get("instagram")),
            "linkedin": handles.get("linkedin_url") or (social_links or {}).get("linkedin"),
            "x": (social_links or {}).get("x"),
            "reddit": (social_links or {}).get("reddit"),
            "youtube": (social_links or {}).get("youtube"),
        }
        return resolved

    async def resolve_batch(
        self,
        candidates: list[dict[str, Any]],
        *,
        region: str | None = None,
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for candidate in candidates:
            socials = await self.resolve_for_company(
                name=candidate.get("name") or candidate.get("company_name") or "",
                website=candidate.get("website"),
                region=region,
                description=candidate.get("description"),
                social_links=candidate.get("social_links") or {},
            )
            enriched.append({**candidate, "socials": socials})
        return enriched


def _handle_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"instagram\.com/([A-Za-z0-9._]+)", url, re.I)
    return match.group(1).lower() if match else None
