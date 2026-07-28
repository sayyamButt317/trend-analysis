from langgraph.graph import END, START, StateGraph

from agents.trend.Nodes.AggregateTrends import AggregateTrendsNode
from agents.trend.Nodes.AggregateViralTrends import AggregateViralTrendsNode
from agents.trend.Nodes.CalculateEngagement import CalculateEngagementNode
from agents.trend.Nodes.CalculateTrendScore import CalculateTrendScoreNode
from agents.trend.Nodes.ClassifyTopics import ClassifyTopicsNode
from agents.trend.Nodes.DetectVirality import DetectViralityNode
from agents.trend.Nodes.DiscoverContent import DiscoverContentNode
from agents.trend.Nodes.ExtractAudio import ExtractAudioNode
from agents.trend.Nodes.ExtractHashtags import ExtractHashtagsNode
from agents.trend.Nodes.ExtractPostData import ExtractPostDataNode
from agents.trend.Nodes.FilterDuplicatePosts import FilterDuplicatePostsNode
from agents.trend.Nodes.GenerateTrendSummary import GenerateTrendSummaryNode
from agents.trend.Nodes.SaveTrendResults import SaveTrendResultsNode
from agents.trend.state.trend_state import TrendState

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
trend_graph.add_node("generate_trend_summary", GenerateTrendSummaryNode)
trend_graph.add_node("save_trend_results", SaveTrendResultsNode)

trend_graph.add_edge(START, "discover_content")
trend_graph.add_edge("discover_content", "extract_post_data")
trend_graph.add_edge("extract_post_data", "filter_duplicate_posts")
trend_graph.add_edge("filter_duplicate_posts", "calculate_engagement")
trend_graph.add_edge("calculate_engagement", "extract_hashtags")
trend_graph.add_edge("extract_hashtags", "extract_audio")
trend_graph.add_edge("extract_audio", "classify_topics")
trend_graph.add_edge("classify_topics", "detect_virality")
trend_graph.add_edge("detect_virality", "aggregate_viral_trends")
trend_graph.add_edge("aggregate_viral_trends", "aggregate_trends")
trend_graph.add_edge("aggregate_trends", "calculate_trend_score")
trend_graph.add_edge("calculate_trend_score", "generate_trend_summary")
trend_graph.add_edge("generate_trend_summary", "save_trend_results")
trend_graph.add_edge("save_trend_results", END)

trend_graph_app = trend_graph.compile()
