from langgraph.graph import END, START, StateGraph

from agents.competitor.node.AnalyzeContentMix import AnalyzeContentMixNode
from agents.competitor.node.CalculateEngagement import CalculateEngagementNode
from agents.competitor.node.ClassifyTopics import ClassifyTopicsNode
from agents.competitor.node.ExtractHashtags import ExtractHashtagsNode
from agents.competitor.node.ExtractPostData import ExtractPostDataNode
from agents.competitor.node.FilterDuplicatePosts import FilterDuplicatePostsNode
from agents.nichetrend.Nodes.DiscoverNicheContent import DiscoverNicheContentNode
from agents.trend.Nodes.AggregateTrends import AggregateTrendsNode
from agents.trend.Nodes.AggregateViralTrends import AggregateViralTrendsNode
from agents.trend.Nodes.CalculateTrendScore import CalculateTrendScoreNode
from agents.trend.Nodes.DetectVirality import DetectViralityNode
from agents.trend.Nodes.ExtractAudio import ExtractAudioNode
from agents.trend.Nodes.GenerateTrendSummary import GenerateTrendSummaryNode
from agents.trend.Nodes.ProcessWebTrends import ProcessWebTrendsNode
from agents.trend.state.trend_state import TrendState


def _route_after_discover(state: TrendState) -> str:
    if state.get("error") and not state.get("raw_posts"):
        return "process_web_trends"
    return "extract_post_data"


def _route_after_instagram_pipeline(state: TrendState) -> str:
    config = state.get("config") or {}
    if config.get("include_web_trends", True):
        return "process_web_trends"
    return "generate_trend_summary"


niche_trend_graph = StateGraph(TrendState)

niche_trend_graph.add_node("discover_niche_content", DiscoverNicheContentNode)
niche_trend_graph.add_node("extract_post_data", ExtractPostDataNode)
niche_trend_graph.add_node("filter_duplicate_posts", FilterDuplicatePostsNode)
niche_trend_graph.add_node("calculate_engagement", CalculateEngagementNode)
niche_trend_graph.add_node("extract_hashtags", ExtractHashtagsNode)
niche_trend_graph.add_node("extract_audio", ExtractAudioNode)
niche_trend_graph.add_node("classify_topics", ClassifyTopicsNode)
niche_trend_graph.add_node("detect_virality", DetectViralityNode)
niche_trend_graph.add_node("aggregate_viral_trends", AggregateViralTrendsNode)
niche_trend_graph.add_node("aggregate_trends", AggregateTrendsNode)
niche_trend_graph.add_node("calculate_trend_score", CalculateTrendScoreNode)
niche_trend_graph.add_node("analyze_competitor_strategies", AnalyzeContentMixNode)
niche_trend_graph.add_node("process_web_trends", ProcessWebTrendsNode)
niche_trend_graph.add_node("generate_trend_summary", GenerateTrendSummaryNode)

niche_trend_graph.add_edge(START, "discover_niche_content")
niche_trend_graph.add_conditional_edges(
    "discover_niche_content",
    _route_after_discover,
    {
        "extract_post_data": "extract_post_data",
        "process_web_trends": "process_web_trends",
    },
)
niche_trend_graph.add_edge("extract_post_data", "filter_duplicate_posts")
niche_trend_graph.add_edge("filter_duplicate_posts", "calculate_engagement")
niche_trend_graph.add_edge("calculate_engagement", "extract_hashtags")
niche_trend_graph.add_edge("extract_hashtags", "extract_audio")
niche_trend_graph.add_edge("extract_audio", "classify_topics")
niche_trend_graph.add_edge("classify_topics", "detect_virality")
niche_trend_graph.add_edge("detect_virality", "aggregate_viral_trends")
niche_trend_graph.add_edge("aggregate_viral_trends", "aggregate_trends")
niche_trend_graph.add_edge("aggregate_trends", "calculate_trend_score")
niche_trend_graph.add_edge("calculate_trend_score", "analyze_competitor_strategies")
niche_trend_graph.add_conditional_edges(
    "analyze_competitor_strategies",
    _route_after_instagram_pipeline,
    {
        "process_web_trends": "process_web_trends",
        "generate_trend_summary": "generate_trend_summary",
    },
)
niche_trend_graph.add_edge("process_web_trends", "generate_trend_summary")
niche_trend_graph.add_edge("generate_trend_summary", END)

niche_trend_graph_app = niche_trend_graph.compile()
