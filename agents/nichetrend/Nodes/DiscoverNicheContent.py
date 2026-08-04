import logging
from agents.competitor.node.DiscoverCompetitors import DiscoverCompetitorsNode
from agents.competitor.node.DiscoverCompetitors import DiscoverCompetitorsNode
from agents.nichetrend.Nodes.AnalyzeCompanySocial import AnalyzeCompanySocialNode
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


async def DiscoverNicheContentNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    company_name = config.get("company_name") or (config.get("company") or {}).get("name") or "company"
    region = config.get("region") or (config.get("filters") or {}).get("region")

    logger.info(
        "Niche trend mode: analyzing company social + discovering competitors for %s in %s",
        company_name,
        region,
    )
    state = await DiscoverCompetitorsNode(state)
    return await AnalyzeCompanySocialNode(state)
