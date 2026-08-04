import logging
import re

from config.credential_config import config
from models.website import WebsiteIntelligence
from prompts.company_analysis import SYSTEM_PROMPT as WEBSITE_EXTRACT_PROMPT
from service.Competitor.openai_client import chat_completion_json

logger = logging.getLogger(__name__)

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"instagram\.com/([A-Za-z0-9._]+)", re.I),
    "linkedin": re.compile(r"linkedin\.com/(company|in)/([A-Za-z0-9_-]+)", re.I),
    "x": re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)", re.I),
    "reddit": re.compile(r"reddit\.com/(?:r|u)/([A-Za-z0-9_]+)", re.I),
    "youtube": re.compile(r"youtube\.com/(?:@|channel/|c/)([A-Za-z0-9._-]+)", re.I),
}


def _extract_social_links(text: str, links: list[str] | None = None) -> dict[str, str]:
    found: dict[str, str] = {}
    corpus = text or ""
    for link in links or []:
        corpus += f"\n{link}"
    for platform, pattern in SOCIAL_PATTERNS.items():
        match = pattern.search(corpus)
        if match:
            if platform == "linkedin":
                found[platform] = f"https://www.linkedin.com/{match.group(1)}/{match.group(2)}/"
            else:
                handle = match.group(1)
                if platform == "instagram":
                    found[platform] = f"https://www.instagram.com/{handle}/"
                elif platform == "x":
                    found[platform] = f"https://x.com/{handle}"
                elif platform == "reddit":
                    found[platform] = f"https://www.reddit.com/r/{handle}"
                elif platform == "youtube":
                    found[platform] = f"https://www.youtube.com/@{handle}"
    return found


class WebsiteExtractor:
    async def extract_from_markdown(
        self,
        *,
        url: str,
        markdown: str,
        links: list[str] | None = None,
        company_name: str = "",
    ) -> WebsiteIntelligence:
        social_links = _extract_social_links(markdown, links)
        if not markdown or len(markdown.strip()) < 80:
            return WebsiteIntelligence(
                url=url,
                company_name=company_name,
                social_links=social_links,
                confidence=0.1,
                raw_markdown=markdown or "",
            )

        api_key = (config.OPENAI_API_KEY or "").strip()
        if not api_key:
            return WebsiteIntelligence(
                url=url,
                company_name=company_name,
                description=markdown[:500],
                keywords=re.findall(r"\b[A-Za-z]{4,}\b", markdown)[:15],
                social_links=social_links,
                confidence=0.2,
                raw_markdown=markdown,
            )

        prompt = f"""Extract structured company intelligence from this website content.

Company hint: {company_name}
URL: {url}

Content:
{markdown[:12000]}

Return JSON with keys:
company_name, description, products, services, pricing_model, industries,
target_audience, features, technologies, keywords, business_model, positioning, competitors
"""
        try:
            data = await chat_completion_json(
                temperature=0.1,
                messages=[
                    {"role": "system", "content": WEBSITE_EXTRACT_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            return WebsiteIntelligence(
                url=url,
                company_name=data.get("company_name") or company_name,
                description=data.get("description") or "",
                products=[str(x) for x in data.get("products") or []],
                services=[str(x) for x in data.get("services") or []],
                pricing_model=str(data.get("pricing_model") or ""),
                industries=[str(x) for x in data.get("industries") or []],
                target_audience=[str(x) for x in data.get("target_audience") or []],
                features=[str(x) for x in data.get("features") or []],
                technologies=[str(x) for x in data.get("technologies") or []],
                keywords=[str(x) for x in data.get("keywords") or []],
                business_model=str(data.get("business_model") or ""),
                positioning=str(data.get("positioning") or ""),
                competitors=[str(x) for x in data.get("competitors") or []],
                social_links=social_links,
                confidence=0.75,
                raw_markdown=markdown,
            )
        except Exception:
            logger.exception("Website LLM extraction failed for %s", url)
            return WebsiteIntelligence(
                url=url,
                company_name=company_name,
                description=markdown[:500],
                social_links=social_links,
                confidence=0.25,
                raw_markdown=markdown,
            )
