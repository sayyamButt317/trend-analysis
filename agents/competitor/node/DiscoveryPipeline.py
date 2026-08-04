import logging

from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from models.search_intelligence import SearchIntelligence
from service.Competitor.company_intelligence_builder import CompanyIntelligenceBuilder
from service.Competitor.company_verifier import CompanyVerifier

logger = logging.getLogger(__name__)


async def DiscoveryPipelineNode(state: CompetitorState) -> CompetitorState:
    """Run Tavily + Firecrawl + social discovery and verify candidates."""
    if state.get("error"):
        return state

    config = state.get("config") or {}
    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")
    runtime = config.get("runtime_profile") or {}
    candidate_multiplier = int(runtime.get("discovery_candidate_multiplier") or 3)
    competitor_limit = int(
        filters.get("competitor_limit") or config.get("competitor_limit") or 50
    )

    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data)
    search_data = state.get("search_intelligence") or config.get("search_intelligence") or {}
    search_intel = SearchIntelligence(**{**search_data, "company_name": company.name})

    builder = CompanyIntelligenceBuilder()
    candidates = await builder.discover_candidates(
        company=company,
        search_intel=search_intel,
        region=region,
        limit=competitor_limit * candidate_multiplier,
        max_tavily_queries=int(runtime.get("max_tavily_queries") or 20),
        max_firecrawl_queries=int(runtime.get("max_firecrawl_queries") or 8),
    )

    verifier = CompanyVerifier()
    verified = verifier.verify(
        company=company,
        candidates=candidates,
        region=region,
        limit=competitor_limit,
    )

    website_intel = state.get("web_crawl")
    own_socials = (website_intel or {}).get("social_links") or {}
    intelligence = builder.build_company_intelligence(
        company=company,
        website_intel=website_intel,
        search_results=verified,
        socials=own_socials,
    )

    state["discovery_candidates"] = candidates
    state["verified_competitors"] = verified
    state["discovered_influencers"] = verified
    state["competitors"] = verified
    state["company_analysis"] = {
        **(state.get("company_analysis") or {}),
        "intelligence": intelligence.model_dump(),
    }
    config["discovery_source"] = "tavily+firecrawl+social"
    config["filters_applied"] = {
        **(config.get("filters_applied") or {}),
        "region": region,
        "competitor_limit": competitor_limit,
        "candidate_pool_size": len(candidates),
        "verified_count": len(verified),
        "matching_mode": "intelligence_pipeline",
    }
    state["config"] = config

    if not verified:
        state["error"] = (
            f"No verified competitors found for {company.name} in region '{region}'. "
            "Check FIRECRAWL_API_KEY / TRAVILY_API_KEY or broaden region."
        )
    return state
