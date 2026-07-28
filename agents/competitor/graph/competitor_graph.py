from langgraph.graph import END, START, StateGraph
from agents.competitor.node.AnalyzeContentMix import AnalyzeContentMixNode
from agents.competitor.node.CalculateEngagement import CalculateEngagementNode
from agents.competitor.node.ClassifyTopics import ClassifyTopicsNode
from agents.competitor.node.DiscoverCompetitors import DiscoverCompetitorsNode
from agents.competitor.node.ExtractHashtags import ExtractHashtagsNode
from agents.competitor.node.ExtractPostData import ExtractPostDataNode
from agents.competitor.node.FilterDuplicatePosts import FilterDuplicatePostsNode
from agents.competitor.node.GenerateCompetitorSummary import GenerateCompetitorSummaryNode
from agents.trend.state.trend_state import TrendState

competitor_graph = StateGraph(TrendState)

competitor_graph.add_node("discover_competitors", DiscoverCompetitorsNode)
competitor_graph.add_node("extract_post_data", ExtractPostDataNode)
competitor_graph.add_node("filter_duplicate_posts", FilterDuplicatePostsNode)
competitor_graph.add_node("calculate_engagement", CalculateEngagementNode)
competitor_graph.add_node("extract_hashtags", ExtractHashtagsNode)
competitor_graph.add_node("classify_topics", ClassifyTopicsNode)
competitor_graph.add_node("analyze_content_mix", AnalyzeContentMixNode)
competitor_graph.add_node("generate_competitor_summary", GenerateCompetitorSummaryNode)

competitor_graph.add_edge(START, "discover_competitors")
competitor_graph.add_edge("discover_competitors", "extract_post_data")
competitor_graph.add_edge("extract_post_data", "filter_duplicate_posts")
competitor_graph.add_edge("filter_duplicate_posts", "calculate_engagement")
competitor_graph.add_edge("calculate_engagement", "extract_hashtags")
competitor_graph.add_edge("extract_hashtags", "classify_topics")
competitor_graph.add_edge("classify_topics", "analyze_content_mix")
competitor_graph.add_edge("analyze_content_mix", "generate_competitor_summary")
competitor_graph.add_edge("generate_competitor_summary", END)

competitor_graph_app = competitor_graph.compile()
