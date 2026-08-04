from langgraph.graph import END, START, StateGraph

from agents.competitor.node.AnalyzeCompetitorInsta import AnalyzeCompetitorInstaNode
from agents.competitor.node.AnalyzeCompetitorlinkedin import AnalyzeCompetitorLinkedinNode
from agents.competitor.node.AnalyzeContentMix import AnalyzeContentMixNode
from agents.competitor.node.CalculateEngagement import CalculateEngagementNode
from agents.competitor.node.ClassifyTopics import ClassifyTopicsNode
from agents.competitor.node.DiscoverCompetitors import DiscoverCompetitorsNode
from agents.competitor.node.DiscoveryPipeline import DiscoveryPipelineNode
from agents.competitor.node.ExtractHashtags import ExtractHashtagsNode
from agents.competitor.node.ExtractPostData import ExtractPostDataNode
from agents.competitor.node.FilterDuplicatePosts import FilterDuplicatePostsNode
from agents.competitor.node.FindCompetitor import FindCompetitorNode
from agents.competitor.node.GenerateCompetitorSummary import GenerateCompetitorSummaryNode
from agents.competitor.node.SearchIntelligence import SearchIntelligenceNode
from agents.competitor.node.SimilarityAnalysis import SimilarityAnalysisNode
from agents.competitor.node.UnderstandCompany import UnderstandCompanyNode
from agents.trend.state.trend_state import TrendState

competitor_graph = StateGraph(TrendState)

# Intelligence pipeline
competitor_graph.add_node("understand_company", UnderstandCompanyNode)
competitor_graph.add_node("search_intelligence", SearchIntelligenceNode)
competitor_graph.add_node("discovery_pipeline", DiscoveryPipelineNode)
competitor_graph.add_node("find_competitors", FindCompetitorNode)

# Profile verification + social/content analysis
competitor_graph.add_node("discover_competitors", DiscoverCompetitorsNode)
competitor_graph.add_node("analyze_competitor_instagram", AnalyzeCompetitorInstaNode)
competitor_graph.add_node("analyze_competitor_linkedin", AnalyzeCompetitorLinkedinNode)
competitor_graph.add_node("extract_post_data", ExtractPostDataNode)
competitor_graph.add_node("filter_duplicate_posts", FilterDuplicatePostsNode)
competitor_graph.add_node("calculate_engagement", CalculateEngagementNode)
competitor_graph.add_node("extract_hashtags", ExtractHashtagsNode)
competitor_graph.add_node("classify_topics", ClassifyTopicsNode)
competitor_graph.add_node("analyze_content_mix", AnalyzeContentMixNode)
competitor_graph.add_node("similarity_analysis", SimilarityAnalysisNode)
competitor_graph.add_node("generate_competitor_summary", GenerateCompetitorSummaryNode)

competitor_graph.add_edge(START, "understand_company")
competitor_graph.add_edge("understand_company", "search_intelligence")
competitor_graph.add_edge("search_intelligence", "discovery_pipeline")
competitor_graph.add_edge("discovery_pipeline", "find_competitors")
competitor_graph.add_edge("find_competitors", "discover_competitors")
competitor_graph.add_edge("discover_competitors", "analyze_competitor_instagram")
competitor_graph.add_edge("analyze_competitor_instagram", "analyze_competitor_linkedin")
competitor_graph.add_edge("analyze_competitor_linkedin", "extract_post_data")
competitor_graph.add_edge("extract_post_data", "filter_duplicate_posts")
competitor_graph.add_edge("filter_duplicate_posts", "calculate_engagement")
competitor_graph.add_edge("calculate_engagement", "extract_hashtags")
competitor_graph.add_edge("extract_hashtags", "classify_topics")
competitor_graph.add_edge("classify_topics", "analyze_content_mix")
competitor_graph.add_edge("analyze_content_mix", "similarity_analysis")
competitor_graph.add_edge("similarity_analysis", "generate_competitor_summary")
competitor_graph.add_edge("generate_competitor_summary", END)

competitor_graph_app = competitor_graph.compile()
