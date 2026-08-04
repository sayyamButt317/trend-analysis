import logging

from config.credential_config import config
from models.company import CompanyProfile
from models.search_intelligence import SearchIntelligence
from prompts.search_intelligence import SYSTEM_PROMPT
from service.Competitor.openai_client import chat_completion_json, resolve_openai_model

logger = logging.getLogger(__name__)


class SearchIntelligenceService:
    async def generate(self, company: CompanyProfile, *, region: str | None = None) -> SearchIntelligence:
        region_label = region or company.region or company.country or "Global"
        if not (config.OPENAI_API_KEY or "").strip():
            return self._heuristic(company, region=region_label)

        prompt = f"""
Company profile:
{company.model_dump_json(indent=2)}

Target region: {region_label}

Generate every useful search query for competitor discovery.
Focus on semantic searches instead of exact name searches.

Return JSON with keys:
company_name, search_queries, search_keywords, industry_terms, product_terms,
audience_terms, alternative_names, competitor_patterns, excluded_terms, confidence
"""
        try:
            data = await chat_completion_json(
                model=resolve_openai_model(),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            return SearchIntelligence(
                company_name=data.get("company_name") or company.name,
                search_queries=[str(x) for x in data.get("search_queries") or []][:30],
                search_keywords=[str(x) for x in data.get("search_keywords") or []][:25],
                industry_terms=[str(x) for x in data.get("industry_terms") or []][:15],
                product_terms=[str(x) for x in data.get("product_terms") or []][:15],
                audience_terms=[str(x) for x in data.get("audience_terms") or []][:15],
                alternative_names=[str(x) for x in data.get("alternative_names") or []][:10],
                competitor_patterns=[str(x) for x in data.get("competitor_patterns") or []][:10],
                excluded_terms=[str(x) for x in data.get("excluded_terms") or []][:10],
                confidence=float(data.get("confidence") or 0.7),
            )
        except Exception:
            logger.exception("Search intelligence generation failed")
            return self._heuristic(company, region=region_label)

    def _heuristic(self, company: CompanyProfile, *, region: str) -> SearchIntelligence:
        services = company.services[:5] or company.products[:5] or [company.industry or "software"]
        queries = []
        for term in services:
            queries.extend(
                [
                    f"{term} companies {region}",
                    f"{term} agency {region} instagram",
                    f"top {term} startups {region}",
                    f"{term} alternatives {region}",
                ]
            )
        queries.extend(
            [
                f"companies similar to {company.name} {region}",
                f"{company.industry or 'IT services'} competitors {region}",
            ]
        )
        keywords = list(
            dict.fromkeys(
                [
                    *(company.keywords or []),
                    *(company.services or []),
                    *(company.products or []),
                    *(company.technologies or []),
                ]
            )
        )
        return SearchIntelligence(
            company_name=company.name,
            search_queries=list(dict.fromkeys(queries))[:25],
            search_keywords=keywords[:20],
            industry_terms=[company.industry or "", company.category or "", company.niche or ""],
            product_terms=company.products[:10],
            audience_terms=company.target_audience[:10],
            alternative_names=[],
            competitor_patterns=["agency", "consulting", "SaaS", "software house"],
            excluded_terms=["jobs", "course", "news", "wikipedia"],
            confidence=0.5,
        )
