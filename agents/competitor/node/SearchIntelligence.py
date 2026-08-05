import logging

from agents.competitor.node.discovery_utils import has_manual_competitors
from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.searchintelligence import SearchIntelligenceService

logger = logging.getLogger(__name__)


async def SearchIntelligenceNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    discovery_source = str(config.get("discovery_source") or "").strip().lower()
    existing = state.get("verified_competitors") or state.get("discovered_influencers") or []

    if has_manual_competitors(config) or discovery_source == "manual":
        log_event(
            "2_discovery",
            "Skipping search intelligence — user-provided competitors",
            count=len(existing) or len((config.get("filters") or {}).get("competitors") or []),
        )
        return state

    if existing and discovery_source in {"openai_competitor_proposal", "manual"}:
        log_event(
            "2_discovery",
            "Skipping search intelligence — competitors already proposed",
            count=len(existing),
            source=discovery_source,
        )
        return state

    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")

    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data) if profile_data.get("name") else CompanyProfile(name="Company")

    log_event("2_discovery", "Generating search queries for competitor discovery", company=company.name, region=region)
    service = SearchIntelligenceService()
    intel = await service.generate(company, region=region)

    intel_dict = intel.model_dump()
    state["search_intelligence"] = intel_dict
    config["search_intelligence"] = intel_dict
    state["config"] = config
    log_event(
        "2_discovery",
        "Search intelligence ready",
        queries=len(intel.search_queries or []),
        keywords=len(intel.search_keywords or []),
    )
    return state
