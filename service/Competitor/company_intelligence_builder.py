import logging
from typing import Any
from urllib.parse import urlparse

from models.competitor import CompetitorCandidate, SocialProfiles
from models.company import CompanyProfile
from models.company_intelligence import CompanyIntelligence, SearchInformation, SocialProfile, WebsiteInformation
from models.search import DiscoveryCandidate
from models.search_intelligence import SearchIntelligence
from service.Competitor.firecrawl_service import FirecrawlService
from service.Competitor.social_resolver import SocialResolverService
from service.Competitor.tavily_discovery import TavilyDiscoveryService

logger = logging.getLogger(__name__)


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


class CompanyIntelligenceBuilder:
    def __init__(self) -> None:
        self.tavily = TavilyDiscoveryService()
        self.firecrawl = FirecrawlService()
        self.social = SocialResolverService()

    async def discover_candidates(
        self,
        *,
        company: CompanyProfile,
        search_intel: SearchIntelligence,
        region: str | None = None,
        limit: int = 50,
        max_tavily_queries: int = 20,
        max_firecrawl_queries: int = 8,
    ) -> list[dict[str, Any]]:
        queries = list(dict.fromkeys(search_intel.search_queries))[:max_tavily_queries]
        tavily_candidates = await self.tavily.discover(queries)

        firecrawl_candidates: list[DiscoveryCandidate] = []
        if self.firecrawl.available:
            for query in queries[:max_firecrawl_queries]:
                for item in self.firecrawl.search_web(query, limit=5):
                    url = item.get("url") or item.get("link") or ""
                    if not url:
                        continue
                    firecrawl_candidates.append(
                        DiscoveryCandidate(
                            company_name=(item.get("title") or item.get("name") or "")[:120],
                            website=url,
                            description=(item.get("description") or item.get("snippet") or "")[:500],
                            source_query=query,
                            tavily_score=float(item.get("score") or 0.5),
                            title=(item.get("title") or "")[:120],
                        )
                    )

        merged: dict[str, dict[str, Any]] = {}
        own_domain = _domain(company.website or "")

        for pool in (tavily_candidates, firecrawl_candidates):
            for item in pool:
                key = _domain(item.website) or item.company_name.lower()
                if not key or (own_domain and own_domain in key):
                    continue
                if key in merged:
                    merged[key]["confidence"] = max(
                        merged[key]["confidence"],
                        float(item.tavily_score or 0),
                    )
                    continue
                merged[key] = {
                    "name": item.company_name or item.title,
                    "website": item.website,
                    "description": item.description,
                    "source": "tavily" if pool is tavily_candidates else "firecrawl",
                    "source_query": item.source_query,
                    "confidence": float(item.tavily_score or 0.4),
                    "social_links": {},
                }

        for hint in company.competitors_hint:
            if hint.lower() not in merged:
                merged[hint.lower()] = {
                    "name": hint,
                    "website": None,
                    "description": "",
                    "source": "company_hint",
                    "source_query": "competitors_hint",
                    "confidence": 0.55,
                    "social_links": {},
                }

        candidates = list(merged.values())
        candidates.sort(key=lambda item: float(item.get("confidence") or 0), reverse=True)
        resolved = await self.social.resolve_batch(candidates[: limit * 2], region=region)
        return resolved[:limit]

    def build_company_intelligence(
        self,
        *,
        company: CompanyProfile,
        website_intel: dict[str, Any] | None,
        search_results: list[dict[str, Any]],
        socials: dict[str, str | None],
    ) -> CompanyIntelligence:
        website_info = None
        if website_intel:
            website_info = WebsiteInformation(
                url=website_intel.get("url") or company.website or "",
                title=company.name,
                description=website_intel.get("description") or company.description or "",
                products=list(website_intel.get("products") or company.products),
                services=list(website_intel.get("services") or company.services),
                industries=list(website_intel.get("industries") or []),
                audience=list(website_intel.get("target_audience") or company.target_audience),
                technologies=list(website_intel.get("technologies") or company.technologies),
                keywords=list(website_intel.get("keywords") or company.keywords),
            )

        social_profiles = []
        for platform, handle in (socials or {}).items():
            if handle:
                social_profiles.append(
                    SocialProfile(platform=platform, username=str(handle), url=str(handle))
                )

        return CompanyIntelligence(
            name=company.name,
            confidence=company.confidence,
            website=website_info,
            search_results=[
                SearchInformation(
                    source=item.get("source") or "search",
                    title=item.get("name") or "",
                    url=item.get("website") or "",
                    snippet=item.get("description") or "",
                    score=float(item.get("confidence") or 0),
                )
                for item in search_results[:20]
            ],
            socials=social_profiles,
            competitors=[item.get("name") for item in search_results[:10] if item.get("name")],
            reasoning=f"Built from {company.source} profile with {len(search_results)} discovery hits",
        )

    def to_competitor_candidates(
        self,
        discovered: list[dict[str, Any]],
    ) -> list[CompetitorCandidate]:
        results: list[CompetitorCandidate] = []
        for item in discovered:
            socials = item.get("socials") or {}
            results.append(
                CompetitorCandidate(
                    name=item.get("name") or "Unknown",
                    website=item.get("website"),
                    description=item.get("description"),
                    industry=item.get("industry"),
                    socials=SocialProfiles(
                        instagram=socials.get("instagram"),
                        linkedin=socials.get("linkedin"),
                        reddit=socials.get("reddit"),
                        x=socials.get("x"),
                        youtube=socials.get("youtube"),
                    ),
                    source=item.get("source") or "discovery",
                    confidence=float(item.get("confidence") or 0),
                    reasoning=item.get("source_query"),
                )
            )
        return results
