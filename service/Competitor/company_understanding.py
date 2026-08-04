import logging

from config.credential_config import config
from models.company import CompanyInput, CompanyProfile
from prompts.company_analysis import SYSTEM_PROMPT
from service.Competitor.openai_client import chat_completion_json, resolve_openai_model

logger = logging.getLogger(__name__)


class CompanyUnderstandingService:
    def __init__(self) -> None:
        self.model = resolve_openai_model()

    async def analyze(
        self,
        company: CompanyInput,
        *,
        website_intel: dict | None = None,
    ) -> CompanyProfile:
        prompt = self._build_prompt(company, website_intel=website_intel)
        if not (config.OPENAI_API_KEY or "").strip():
            return self._fallback_profile(company, website_intel=website_intel)

        try:
            data = await chat_completion_json(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            profile = CompanyProfile(
                name=data.get("name") or company.name,
                website=data.get("website") or company.website,
                description=data.get("description") or company.description,
                industry=data.get("industry") or company.industry,
                category=data.get("category"),
                niche=data.get("niche"),
                business_model=data.get("business_model"),
                pricing_model=data.get("pricing_model"),
                target_audience=[str(x) for x in data.get("target_audience") or []],
                products=[str(x) for x in data.get("products") or []],
                services=[str(x) for x in data.get("services") or []],
                features=[str(x) for x in data.get("features") or []],
                technologies=[str(x) for x in data.get("technologies") or []],
                keywords=[str(x) for x in data.get("keywords") or []],
                positioning=data.get("positioning"),
                value_proposition=data.get("value_proposition"),
                countries=[str(x) for x in data.get("countries") or []],
                competitors_hint=[str(x) for x in data.get("competitors_hint") or []],
                country=company.country,
                city=company.city,
                region=company.region,
                source="llm",
            )
            profile.confidence = self._calculate_confidence(profile, company)
            return profile
        except Exception as exc:
            logger.warning(
                "Company understanding LLM unavailable for %s (%s); using heuristic profile",
                company.name,
                exc,
            )
            return self._fallback_profile(company, website_intel=website_intel)

    def _fallback_profile(
        self,
        company: CompanyInput,
        *,
        website_intel: dict | None = None,
    ) -> CompanyProfile:
        website = website_intel or {}
        return CompanyProfile(
            name=company.name,
            website=company.website,
            description=company.description or website.get("description"),
            industry=company.industry,
            services=list(website.get("services") or []),
            products=list(website.get("products") or []),
            keywords=list(website.get("keywords") or []),
            target_audience=list(website.get("target_audience") or []),
            positioning=website.get("positioning"),
            business_model=website.get("business_model"),
            country=company.country,
            city=company.city,
            region=company.region,
            confidence=0.35,
            source="heuristic",
        )

    def _build_prompt(self, company: CompanyInput, *, website_intel: dict | None = None) -> str:
        website_block = ""
        if website_intel:
            website_block = f"\nWebsite intelligence:\n{website_intel}\n"
        return f"""
Company Name: {company.name}
Website: {company.website or 'unknown'}
Industry: {company.industry or 'unknown'}
Description: {company.description or company.profile_text or 'unknown'}
Country: {company.country or 'unknown'}
City: {company.city or 'unknown'}
Region: {company.region or 'unknown'}
{website_block}

Return JSON with keys:
name, website, description, industry, category, niche, business_model, pricing_model,
target_audience, products, services, features, technologies, keywords, positioning,
value_proposition, countries, competitors_hint
"""

    def _calculate_confidence(self, profile: CompanyProfile, company: CompanyInput) -> float:
        score = 0
        if profile.industry:
            score += 10
        if profile.business_model:
            score += 10
        if profile.products:
            score += 15
        if profile.services:
            score += 15
        if profile.positioning:
            score += 15
        if profile.target_audience:
            score += 15
        if profile.keywords:
            score += 10
        if profile.value_proposition:
            score += 10
        if company.website:
            score += 10
        return round(score / 100, 2)
