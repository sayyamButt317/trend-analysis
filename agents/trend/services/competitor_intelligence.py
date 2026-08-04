import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from agents.trend.services.company_profile_parser import CompanySignals, parse_company_profile
from config.credential_config import config

logger = logging.getLogger(__name__)


@dataclass
class CompetitorIntel:
    competitor_types: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    instagram_queries: list[str] = field(default_factory=list)
    target_keywords: list[str] = field(default_factory=list)
    ideal_competitor_profile: str = ""
    source: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "competitor_types": self.competitor_types,
            "search_queries": self.search_queries,
            "instagram_queries": self.instagram_queries,
            "target_keywords": self.target_keywords,
            "ideal_competitor_profile": self.ideal_competitor_profile,
            "source": self.source,
        }


def _heuristic_intel(
    *,
    company_name: str,
    region: str,
    signals: CompanySignals,
) -> CompetitorIntel:
    location = region.strip()
    flagship = signals.flagship_services[:3]
    services = signals.services[:6]
    industries = signals.target_industries[:3]

    competitor_types = []
    for service in flagship or services[:3]:
        competitor_types.append(f"{service} companies")
    if industries:
        competitor_types.append(f"IT vendors serving {', '.join(industries)}")

    web_queries = [
        f"{company_name} competitors {location}",
        f"companies similar to {company_name} {location}",
        f"top software development companies {location}",
        f"AI development companies {location}",
        f"IT staff augmentation companies {location}",
    ]
    for service in flagship:
        web_queries.append(f"{service} companies {location}")
    for industry in industries:
        web_queries.append(f"{industry} software development companies {location}")

    instagram_queries = []
    for term in (flagship + services[:3]):
        instagram_queries.extend(
            [
                f"{term} company {location} instagram",
                f"{term} agency {location} instagram",
            ]
        )
    instagram_queries.extend(
        [
            f"software development company {location} instagram",
            f"AI development agency {location} instagram",
            f"IT services company {location} instagram",
        ]
    )

    keywords = list(
        dict.fromkeys(
            [
                *(signals.keywords or []),
                *(flagship or []),
                *(services or []),
                *(signals.technologies or [])[:5],
                "software development",
                "AI development",
                "IT services",
                "staff augmentation",
            ]
        )
    )

    profile_bits = [f"Offers {', '.join(flagship)}" if flagship else ""]
    if industries:
        profile_bits.append(f"Serves {', '.join(industries)} clients")
    profile_bits.append(f"Active in {location}")

    return CompetitorIntel(
        competitor_types=competitor_types[:8],
        search_queries=list(dict.fromkeys(web_queries))[:25],
        instagram_queries=list(dict.fromkeys(instagram_queries))[:35],
        target_keywords=keywords[:30],
        ideal_competitor_profile=". ".join(bit for bit in profile_bits if bit),
        source="heuristic",
    )


async def _llm_intel(
    *,
    company_name: str,
    region: str,
    company_profile: str,
    signals: CompanySignals,
) -> CompetitorIntel | None:
    if not (config.OPENAI_API_KEY or "").strip():
        return None

    prompt = f"""You are a competitive intelligence analyst. Given a company profile and target region, identify who their real business competitors are and how to find them on Instagram.

Company: {company_name}
Target region: {region}
Known services: {", ".join(signals.flagship_services or signals.services[:5])}
Known industries: {", ".join(signals.target_industries[:5])}

Company profile excerpt:
{company_profile[:4000]}

Return ONLY valid JSON with this shape:
{{
  "competitor_types": ["type of companies that compete with them"],
  "search_queries": ["web search queries to find competitor companies in the region"],
  "instagram_queries": ["queries to find competitor Instagram business accounts in the region"],
  "target_keywords": ["keywords that should appear in a true competitor profile"],
  "ideal_competitor_profile": "one sentence describing the ideal competitor to match"
}}
"""

    try:
        from service.Competitor.openai_client import chat_completion_json

        data = await chat_completion_json(
            messages=[
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        return CompetitorIntel(
            competitor_types=[str(x) for x in data.get("competitor_types") or []][:8],
            search_queries=[str(x) for x in data.get("search_queries") or []][:25],
            instagram_queries=[str(x) for x in data.get("instagram_queries") or []][:35],
            target_keywords=[str(x) for x in data.get("target_keywords") or []][:30],
            ideal_competitor_profile=str(data.get("ideal_competitor_profile") or ""),
            source="llm",
        )
    except Exception:
        logger.exception("LLM competitor intelligence failed")
        return None


def _merge_intel(primary: CompetitorIntel, fallback: CompetitorIntel) -> CompetitorIntel:
    return CompetitorIntel(
        competitor_types=list(dict.fromkeys([*primary.competitor_types, *fallback.competitor_types]))[:8],
        search_queries=list(dict.fromkeys([*primary.search_queries, *fallback.search_queries]))[:30],
        instagram_queries=list(
            dict.fromkeys([*primary.instagram_queries, *fallback.instagram_queries])
        )[:40],
        target_keywords=list(dict.fromkeys([*primary.target_keywords, *fallback.target_keywords]))[:35],
        ideal_competitor_profile=primary.ideal_competitor_profile or fallback.ideal_competitor_profile,
        source=primary.source if primary.source == "llm" else fallback.source,
    )


async def build_competitor_intelligence(
    *,
    company_name: str,
    region: str,
    company_profile: str,
    company_signals: dict[str, Any] | None = None,
) -> CompetitorIntel:
    signals = (
        CompanySignals(**company_signals)
        if company_signals
        else parse_company_profile(company_profile, company={"name": company_name})
    )
    heuristic = _heuristic_intel(company_name=company_name, region=region, signals=signals)
    llm_result = await _llm_intel(
        company_name=company_name,
        region=region,
        company_profile=company_profile,
        signals=signals,
    )
    if llm_result:
        merged = _merge_intel(llm_result, heuristic)
        merged.source = "llm+heuristic"
        return merged
    return heuristic
