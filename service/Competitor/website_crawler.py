import logging
from models.website import WebsiteIntelligence
from service.Competitor.firecrawl_service import FirecrawlService
from service.Competitor.website_extractor import WebsiteExtractor

logger = logging.getLogger(__name__)


class WebsiteCrawlerService:
    def __init__(self) -> None:
        self.firecrawl = FirecrawlService()
        self.extractor = WebsiteExtractor()

    async def crawl_company_website(
        self,
        *,
        url: str,
        company_name: str = "",
    ) -> WebsiteIntelligence | None:
        if not url:
            return None
        normalized = url if url.startswith("http") else f"https://{url.lstrip('/')}"
        scrape = self.firecrawl.scrape_url(normalized)
        if not scrape.get("markdown"):
            logger.info("No Firecrawl content for %s", normalized)
            return None
        return await self.extractor.extract_from_markdown(
            url=normalized,
            markdown=scrape.get("markdown") or "",
            links=scrape.get("links") or [],
            company_name=company_name,
        )
