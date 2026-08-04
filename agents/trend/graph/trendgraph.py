from langgraph.graph import END, START, StateGraph

from agents.trend.Nodes.DiscoverWebTrends import DiscoverWebTrendsNode
from agents.trend.Nodes.GenerateTrendSummary import GenerateTrendSummaryNode
from agents.trend.Nodes.ProcessWebTrends import ProcessWebTrendsNode
from agents.trend.state.trend_state import TrendState

global_trend_graph = StateGraph(TrendState)

global_trend_graph.add_node("discover_web_trends", DiscoverWebTrendsNode)
global_trend_graph.add_node("process_web_trends", ProcessWebTrendsNode)
global_trend_graph.add_node("generate_trend_summary", GenerateTrendSummaryNode)

global_trend_graph.add_edge(START, "discover_web_trends")
global_trend_graph.add_edge("discover_web_trends", "process_web_trends")
global_trend_graph.add_edge("process_web_trends", "generate_trend_summary")
global_trend_graph.add_edge("generate_trend_summary", END)

trend_graph_app = global_trend_graph.compile()
