import logging

from agents.trend.Nodes.DiscoverWebTrends import DiscoverWebTrendsNode
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


async def DiscoverContentNode(state: TrendState) -> TrendState:
    """Legacy entrypoint — global trend graph uses DiscoverWebTrendsNode directly."""
    return await DiscoverWebTrendsNode(state)
