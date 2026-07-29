from langgraph.graph import END, START, StateGraph
from agents.competitor.node.AnalyzeContentMix import AnalyzeContentMixNode
from agents.competitor.node.CalculateEngagement import CalculateEngagementNode
from agents.competitor.node.ClassifyTopics import ClassifyTopicsNode
from agents.competitor.node.ExtractHashtags import ExtractHashtagsNode
from agents.competitor.node.ExtractPostData import ExtractPostDataNode
from agents.competitor.node.FilterDuplicatePosts import FilterDuplicatePostsNode
from agents.trend.Nodes.AggregateTrends import AggregateTrendsNode
from agents.trend.Nodes.AggregateViralTrends import AggregateViralTrendsNode
from agents.trend.Nodes.CalculateTrendScore import CalculateTrendScoreNode
from agents.trend.Nodes.DetectVirality import DetectViralityNode
from agents.trend.Nodes.DiscoverContent import DiscoverContentNode
from agents.trend.Nodes.ExtractAudio import ExtractAudioNode
from agents.trend.Nodes.GenerateTrendSummary import GenerateTrendSummaryNode
from agents.trend.Nodes.ProcessWebTrends import ProcessWebTrendsNode
from agents.trend.state.trend_state import TrendState





def _route_after_discover(state: TrendState) -> str:
    config = state.get("config") or {}
    if config.get("agent_mode") == "global_trend":
        return "process_web_trends"
    if state.get("error") and not state.get("raw_posts"):
        return "process_web_trends"
    return "extract_post_data"





def _route_after_instagram_pipeline(state: TrendState) -> str:
    config = state.get("config") or {}
    if config.get("include_web_trends", True):
        return "process_web_trends"
    return "generate_trend_summary"





trend_graph = StateGraph(TrendState)



trend_graph.add_node("discover_content", DiscoverContentNode)

trend_graph.add_node("extract_post_data", ExtractPostDataNode)

trend_graph.add_node("filter_duplicate_posts", FilterDuplicatePostsNode)

trend_graph.add_node("calculate_engagement", CalculateEngagementNode)

trend_graph.add_node("extract_hashtags", ExtractHashtagsNode)

trend_graph.add_node("extract_audio", ExtractAudioNode)

trend_graph.add_node("classify_topics", ClassifyTopicsNode)

trend_graph.add_node("detect_virality", DetectViralityNode)

trend_graph.add_node("aggregate_viral_trends", AggregateViralTrendsNode)

trend_graph.add_node("aggregate_trends", AggregateTrendsNode)

trend_graph.add_node("calculate_trend_score", CalculateTrendScoreNode)

trend_graph.add_node("analyze_competitor_strategies", AnalyzeContentMixNode)

trend_graph.add_node("process_web_trends", ProcessWebTrendsNode)

trend_graph.add_node("generate_trend_summary", GenerateTrendSummaryNode)



trend_graph.add_edge(START, "discover_content")

trend_graph.add_conditional_edges(

    "discover_content",

    _route_after_discover,

    {

        "extract_post_data": "extract_post_data",

        "process_web_trends": "process_web_trends",

    },

)

trend_graph.add_edge("extract_post_data", "filter_duplicate_posts")

trend_graph.add_edge("filter_duplicate_posts", "calculate_engagement")

trend_graph.add_edge("calculate_engagement", "extract_hashtags")

trend_graph.add_edge("extract_hashtags", "extract_audio")

trend_graph.add_edge("extract_audio", "classify_topics")

trend_graph.add_edge("classify_topics", "detect_virality")

trend_graph.add_edge("detect_virality", "aggregate_viral_trends")

trend_graph.add_edge("aggregate_viral_trends", "aggregate_trends")

trend_graph.add_edge("aggregate_trends", "calculate_trend_score")

trend_graph.add_edge("calculate_trend_score", "analyze_competitor_strategies")

trend_graph.add_conditional_edges(

    "analyze_competitor_strategies",

    _route_after_instagram_pipeline,

    {

        "process_web_trends": "process_web_trends",

        "generate_trend_summary": "generate_trend_summary",

    },

)

trend_graph.add_edge("process_web_trends", "generate_trend_summary")

trend_graph.add_edge("generate_trend_summary", END)



trend_graph_app = trend_graph.compile()

