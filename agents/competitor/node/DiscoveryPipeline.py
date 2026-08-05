import logging

from agents.competitor.node.discovery_utils import has_manual_competitors, manual_competitor_inputs
from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from models.search_intelligence import SearchIntelligence
from service.Competitor.company_intelligence_builder import CompanyIntelligenceBuilder
from service.Competitor.company_verifier import CompanyVerifier
from service.Competitor.platforms import filter_competitor_socials

logger = logging.getLogger(__name__)


async def DiscoveryPipelineNode(state: CompetitorState) -> CompetitorState:
    fatal = state.get("error") or ""
    if fatal and "rate limit" in fatal.lower():
        return state

    config = state.get("config") or {}
    if has_manual_competitors(config) or str(config.get("discovery_source") or "").lower() == "manual":
        log_event(
            "2_discovery",
            "Skipping Tavily/Firecrawl discovery — user-provided competitors",
            count=len(manual_competitor_inputs(config)),
        )
        return state

    existing = state.get("verified_competitors") or state.get("discovered_influencers") or []
    if existing:
        log_event(
            "2_discovery",
            "Skipping Tavily/Firecrawl discovery — competitors already proposed",
            count=len(existing),
            source=config.get("discovery_source"),
        )
        return state
    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")
    runtime = config.get("runtime_profile") or {}
    candidate_multiplier = int(runtime.get("discovery_candidate_multiplier") or 2)
    competitor_limit = int(
        filters.get("competitor_limit") or config.get("competitor_limit") or 10
    )

    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data)
    search_data = state.get("search_intelligence") or config.get("search_intelligence") or {}
    search_intel = SearchIntelligence(**{**search_data, "company_name": company.name})

    builder = CompanyIntelligenceBuilder()
    tavily_ok = builder.tavily.available
    log_event(
        "2_discovery",
        "Discovering candidates via Tavily/Firecrawl",
        company=company.name,
        region=region,
        tavily="configured" if tavily_ok else "missing",
        firecrawl="configured" if builder.firecrawl.available else "missing",
        limit=competitor_limit * candidate_multiplier,
    )
    candidates = await builder.discover_candidates(
        company=company,
        search_intel=search_intel,
        region=region,
        limit=competitor_limit * candidate_multiplier,
        max_tavily_queries=int(runtime.get("max_tavily_queries") or 10),
        max_firecrawl_queries=int(runtime.get("max_firecrawl_queries") or 4),
        max_social_tavily_lookups=int(runtime.get("max_social_tavily_lookups") or 15),
        resolve_linkedin=not bool(config.get("skip_linkedin")),
    )

    log_event(
        "2_discovery",
        "Verifying discovered candidates",
        candidates=len(candidates),
        region=region,
        limit=competitor_limit,
    )
    verifier = CompanyVerifier()
    verified = verifier.verify(
        company=company,
        candidates=candidates,
        region=region,
        limit=competitor_limit,
    )

    website_intel = state.get("web_crawl")
    own_socials = filter_competitor_socials((website_intel or {}).get("social_links") or {})
    intelligence = builder.build_company_intelligence(
        company=company,
        website_intel=website_intel,
        search_results=verified,
        socials=own_socials,
    )

    state["discovery_candidates"] = candidates
    verified = [
        {
            **item,
            "authenticity": item.get("authenticity") or "intelligence_pipeline",
            "source": item.get("source") or "tavily+firecrawl+social",
            "discovery_source": "tavily+firecrawl+social",
        }
        for item in verified
    ]
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
        "discovery_source": "tavily+firecrawl+social",
    }
    state["config"] = config

    if not verified:
        warnings = list((config.get("filters_applied") or {}).get("discovery_warnings") or [])
        warnings.append(
            f"Intelligence pipeline found {len(candidates)} candidate(s) but 0 passed verification "
            f"for region '{region}'. Falling back to Instagram discovery."
        )
        config.setdefault("filters_applied", {})["discovery_warnings"] = warnings
        state["config"] = config
        log_event(
            "2_discovery",
            "No verified competitors — will use Instagram fallback",
            company=company.name,
            region=region,
            candidates=len(candidates),
        )
    else:
        log_event(
            "2_discovery",
            "Verified competitors ready",
            verified=len(verified),
            candidates=len(candidates),
        )
    return state
