import logging

from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.searchintelligence import SearchIntelligenceService

logger = logging.getLogger(__name__)


async def SearchIntelligenceNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")

    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data) if profile_data.get("name") else CompanyProfile(name="Company")

    service = SearchIntelligenceService()
    intel = await service.generate(company, region=region)

    intel_dict = intel.model_dump()
    state["search_intelligence"] = intel_dict
    config["search_intelligence"] = intel_dict
    state["config"] = config
    return state
