import logging
from typing import Any
from models.company import CompanyProfile

logger = logging.getLogger(__name__)

REGION_TERMS = {
    "gcc": ("gcc", "gulf", "uae", "dubai", "saudi", "riyadh", "qatar", "kuwait", "bahrain", "oman"),
    "mena": ("mena", "middle east", "gcc", "uae", "saudi", "egypt", "dubai"),
    "north america": ("usa", "us", "united states", "canada", "north america"),
    "europe": ("europe", "uk", "united kingdom", "germany", "france"),
    "pakistan": ("pakistan", "pk", "lahore", "karachi", "islamabad", "rawalpindi", "faisalabad", "software house"),
    "pk": ("pakistan", "pk", "lahore", "karachi", "islamabad", "rawalpindi"),
    "south asia": ("south asia", "pakistan", "india", "bangladesh", "lahore", "karachi"),
    "asia": ("asia", "south asia", "pakistan", "india", "singapore"),
}


def _region_terms(region: str | None, company: CompanyProfile) -> tuple[str, ...]:
    key = (region or company.region or company.country or "").lower().strip()
    if key in REGION_TERMS:
        return REGION_TERMS[key]
    for map_key, terms in REGION_TERMS.items():
        if map_key in key or key in map_key:
            return terms
    if key:
        return (key, key.replace(" ", ""))
    return ("global",)


def _overlap_score(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    set_a = {item.lower().strip() for item in a if item}
    set_b = {item.lower().strip() for item in b if item}
    if not set_a or not set_b:
        return 0.0
    hits = set_a & set_b
    return min(len(hits) / max(len(set_a), 1), 1.0)


def _text_hits(text: str, terms: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in terms)


class CompetitorRanker:
    def score_candidate(
        self,
        company: CompanyProfile,
        candidate: dict[str, Any],
        *,
        region: str | None = None,
    ) -> dict[str, Any]:
        text = " ".join(
            [
                candidate.get("name") or "",
                candidate.get("description") or "",
                candidate.get("website") or "",
                candidate.get("source_query") or "",
            ]
        ).lower()

        industry_score = _overlap_score(
            [company.industry or "", company.category or "", company.niche or ""],
            [candidate.get("industry") or "", candidate.get("description") or ""],
        )
        if industry_score < 0.2 and company.industry and company.industry.lower() in text:
            industry_score = 0.6

        service_score = _overlap_score(company.services, [text])
        intel = candidate.get("website_intelligence") or {}
        if intel.get("services"):
            service_score = max(service_score, _overlap_score(company.services, intel["services"]))
        product_score = _overlap_score(company.products, [text])
        audience_score = _overlap_score(company.target_audience, [text])
        tech_score = _overlap_score(company.technologies, [text])
        if intel.get("technologies"):
            tech_score = max(tech_score, _overlap_score(company.technologies, intel["technologies"]))

        pricing_score = 0.5 if (company.pricing_model or "").lower() in text else 0.0
        content_score = 0.4 if candidate.get("linkedin_analysis") or candidate.get("instagram_analysis") else 0.2
        social_score = 0.5 if candidate.get("instagram_analysis") else 0.2

        region_terms = _region_terms(region, company)
        source_query = (candidate.get("source_query") or "").lower()
        geography_score = 1.0 if _text_hits(text, region_terms) else 0.2
        if geography_score < 0.5 and region and (region or "").lower() in source_query:
            geography_score = 0.85
        if geography_score < 0.5 and _text_hits(source_query, region_terms):
            geography_score = 0.8
        if company.country and company.country.lower() in text:
            geography_score = max(geography_score, 0.8)
        if company.city and company.city.lower() in text:
            geography_score = max(geography_score, 0.9)

        business_model_score = 0.5 if (company.business_model or "").lower() in text else 0.3
        positioning_score = 0.6 if any(word in text for word in (company.keywords or [])[:8]) else 0.25

        overall = round(
            industry_score * 0.18
            + max(product_score, service_score) * 0.18
            + audience_score * 0.10
            + tech_score * 0.10
            + geography_score * 0.14
            + business_model_score * 0.06
            + positioning_score * 0.10
            + pricing_score * 0.06
            + content_score * 0.04
            + social_score * 0.04,
            3,
        )

        explanation = (
            f"Industry {industry_score:.2f}, services {service_score:.2f}, "
            f"region {geography_score:.2f}, niche keywords {positioning_score:.2f}"
        )
        return {
            "services": round(max(product_score, service_score), 3),
            "industry": round(industry_score, 3),
            "products": round(product_score, 3),
            "audience": round(audience_score, 3),
            "target_audience": round(audience_score, 3),
            "business_model": round(business_model_score, 3),
            "positioning": round(positioning_score, 3),
            "marketing": round(max(positioning_score, social_score), 3),
            "pricing": round(pricing_score, 3),
            "technology": round(tech_score, 3),
            "geography": round(geography_score, 3),
            "location": round(geography_score, 3),
            "social_strategy": round(social_score, 3),
            "content_strategy": round(content_score, 3),
            "content": round(content_score, 3),
            "overall": overall,
            "explanation": explanation,
        }

    def rank_all(
        self,
        company: CompanyProfile,
        candidates: list[dict[str, Any]],
        *,
        region: str | None = None,
    ) -> list[dict[str, Any]]:
        ranked = []
        for candidate in candidates:
            score = self.score_candidate(company, candidate, region=region)
            ranked.append({**candidate, "similarity": score, "match_score": score["overall"]})
        ranked.sort(key=lambda item: float(item.get("match_score") or 0), reverse=True)
        return ranked

    def gap_analysis(
        self,
        company: CompanyProfile,
        competitors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        competitor_services = set()
        competitor_keywords = set()
        for comp in competitors:
            competitor_services.update((comp.get("description") or "").lower().split())
            competitor_keywords.update((comp.get("source_query") or "").lower().split())

        company_services = {s.lower() for s in company.services}
        service_gaps = sorted(competitor_services - company_services)[:10]
        keyword_gaps = sorted(competitor_keywords - {k.lower() for k in company.keywords})[:10]

        return {
            "service_gaps": service_gaps,
            "keyword_gaps": keyword_gaps,
            "competitor_count": len(competitors),
            "summary": (
                f"Identified {len(service_gaps)} service/theme gaps and "
                f"{len(keyword_gaps)} keyword gaps vs {len(competitors)} competitors."
            ),
        }

    def recommendations(
        self,
        company: CompanyProfile,
        gap_analysis: dict[str, Any],
        competitors: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        recs: list[dict[str, Any]] = []
        if gap_analysis.get("service_gaps"):
            recs.append(
                {
                    "type": "content",
                    "priority": "high",
                    "title": "Cover competitor service themes",
                    "detail": f"Create content around: {', '.join(gap_analysis['service_gaps'][:5])}",
                }
            )
        top = competitors[:3]
        if top:
            recs.append(
                {
                    "type": "positioning",
                    "priority": "medium",
                    "title": "Differentiate from top competitors",
                    "detail": f"Top rivals: {', '.join(item.get('name') or '' for item in top)}",
                }
            )
        if company.services:
            recs.append(
                {
                    "type": "seo",
                    "priority": "medium",
                    "title": "Double down on core services",
                    "detail": f"Emphasize: {', '.join(company.services[:4])}",
                }
            )
        return recs
