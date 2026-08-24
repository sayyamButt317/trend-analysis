from langgraph.graph import END, START, StateGraph
from agents.competitor.node.AnalyzeCompetitorInsta import AnalyzeCompetitorInstaNode
from agents.competitor.node.AnalyzeCompetitorlinkedin import AnalyzeCompetitorLinkedinNode
from agents.competitor.node.AnalyzeCompetitorWebsiteNode import AnalyzeCompetitorWebsiteNode
from agents.competitor.node.AnalyzeContentMix import AnalyzeContentMixNode
from agents.competitor.node.AnalyzeUserInsta import AnalyzeUserInstaNode
from agents.competitor.node.AnalyzeUserLinkedIn import AnalyzeUserLinkedInNode
from agents.competitor.node.CalculateEngagement import CalculateEngagementNode
from agents.competitor.node.ClassifyTopics import ClassifyTopicsNode
from agents.competitor.node.DiscoverCompetitors import DiscoverCompetitorsNode
from agents.competitor.node.DiscoveryPipeline import DiscoveryPipelineNode
from agents.competitor.node.ExtractHashtags import ExtractHashtagsNode
from agents.competitor.node.ExtractPostData import ExtractPostDataNode
from agents.competitor.node.FilterDuplicatePosts import FilterDuplicatePostsNode
from agents.competitor.node.FindCompetitor import FindCompetitorNode
from agents.competitor.node.CompetitiveContentIntelligence import CompetitiveContentIntelligenceNode
from agents.competitor.node.CompetitiveGaps import CompetitiveGapsNode
from agents.competitor.node.CompetitorIntelligenceNode import CompetitorIntelligenceNode
from agents.competitor.node.GapAnalysisNode import GapAnalysisNode
from agents.competitor.node.GenerateCompetitorSummary import GenerateCompetitorSummaryNode
from agents.competitor.node.HydrateCompanyContext import (
    HydrateCompanyContextNode,
    route_after_hydrate,
)
from agents.competitor.node.ProposeCompetitorsNode import ProposeCompetitorsNode
from agents.competitor.node.RecommendationNode import RecommendationNode
from agents.competitor.node.SearchIntelligence import SearchIntelligenceNode
from agents.competitor.node.SimilarityAnalysis import SimilarityAnalysisNode
from agents.competitor.node.UnderstandCompany import UnderstandCompanyNode
from agents.competitor.pipeline_log import with_pipeline_log
from agents.trend.state.trend_state import TrendState


competitor_graph = StateGraph(TrendState)

# Phase 0/1: reuse analyze-company handoff when provided; otherwise analyze company in-pipeline
competitor_graph.add_node("hydrate_company_context", with_pipeline_log("hydrate_company_context", HydrateCompanyContextNode))
competitor_graph.add_node("understand_company", with_pipeline_log("understand_company", UnderstandCompanyNode))
competitor_graph.add_node("analyze_user_instagram", with_pipeline_log("analyze_user_instagram", AnalyzeUserInstaNode))
competitor_graph.add_node("analyze_user_linkedin", with_pipeline_log("analyze_user_linkedin", AnalyzeUserLinkedInNode))

# Phase 2: OpenAI proposal first; Tavily path only as fallback if proposal empty
competitor_graph.add_node("propose_competitors", with_pipeline_log("propose_competitors", ProposeCompetitorsNode))
competitor_graph.add_node("search_intelligence", with_pipeline_log("search_intelligence", SearchIntelligenceNode))
competitor_graph.add_node("discovery_pipeline", with_pipeline_log("discovery_pipeline", DiscoveryPipelineNode))
competitor_graph.add_node("find_competitors", with_pipeline_log("find_competitors", FindCompetitorNode))
competitor_graph.add_node("discover_competitors", with_pipeline_log("discover_competitors", DiscoverCompetitorsNode))

# Phase 3: competitor analysis
competitor_graph.add_node("analyze_competitor_website", with_pipeline_log("analyze_competitor_website", AnalyzeCompetitorWebsiteNode))
competitor_graph.add_node("analyze_competitor_instagram", with_pipeline_log("analyze_competitor_instagram", AnalyzeCompetitorInstaNode))
competitor_graph.add_node("analyze_competitor_linkedin", with_pipeline_log("analyze_competitor_linkedin", AnalyzeCompetitorLinkedinNode))
competitor_graph.add_node("extract_post_data", with_pipeline_log("extract_post_data", ExtractPostDataNode))
competitor_graph.add_node("filter_duplicate_posts", with_pipeline_log("filter_duplicate_posts", FilterDuplicatePostsNode))
competitor_graph.add_node("calculate_engagement", with_pipeline_log("calculate_engagement", CalculateEngagementNode))
competitor_graph.add_node("extract_hashtags", with_pipeline_log("extract_hashtags", ExtractHashtagsNode))
competitor_graph.add_node("classify_topics", with_pipeline_log("classify_topics", ClassifyTopicsNode))
competitor_graph.add_node("analyze_content_mix", with_pipeline_log("analyze_content_mix", AnalyzeContentMixNode))

# Phase 4: strategy
competitor_graph.add_node("similarity_analysis", with_pipeline_log("similarity_analysis", SimilarityAnalysisNode))
competitor_graph.add_node("gap_analysis", with_pipeline_log("gap_analysis", GapAnalysisNode))
competitor_graph.add_node("competitive_gaps", with_pipeline_log("competitive_gaps", CompetitiveGapsNode))
competitor_graph.add_node(
    "competitive_content_intelligence",
    with_pipeline_log("competitive_content_intelligence", CompetitiveContentIntelligenceNode),
)
competitor_graph.add_node("competitor_intelligence", with_pipeline_log("competitor_intelligence", CompetitorIntelligenceNode))
competitor_graph.add_node("recommendations", with_pipeline_log("recommendations", RecommendationNode))
competitor_graph.add_node("generate_competitor_summary", with_pipeline_log("generate_competitor_summary", GenerateCompetitorSummaryNode))

competitor_graph.add_edge(START, "hydrate_company_context")
competitor_graph.add_conditional_edges(
    "hydrate_company_context",
    route_after_hydrate,
    {
        "propose_competitors": "propose_competitors",
        "understand_company": "understand_company",
    },
)
competitor_graph.add_edge("understand_company", "analyze_user_instagram")
competitor_graph.add_edge("analyze_user_instagram", "analyze_user_linkedin")
competitor_graph.add_edge("analyze_user_linkedin", "propose_competitors")
competitor_graph.add_edge("propose_competitors", "search_intelligence")
competitor_graph.add_edge("search_intelligence", "discovery_pipeline")
competitor_graph.add_edge("discovery_pipeline", "find_competitors")
competitor_graph.add_edge("find_competitors", "discover_competitors")
competitor_graph.add_edge("discover_competitors", "analyze_competitor_website")
competitor_graph.add_edge("analyze_competitor_website", "analyze_competitor_instagram")
competitor_graph.add_edge("analyze_competitor_instagram", "analyze_competitor_linkedin")
competitor_graph.add_edge("analyze_competitor_linkedin", "extract_post_data")
competitor_graph.add_edge("extract_post_data", "filter_duplicate_posts")
competitor_graph.add_edge("filter_duplicate_posts", "calculate_engagement")
competitor_graph.add_edge("calculate_engagement", "extract_hashtags")
competitor_graph.add_edge("extract_hashtags", "classify_topics")
competitor_graph.add_edge("classify_topics", "analyze_content_mix")
competitor_graph.add_edge("analyze_content_mix", "similarity_analysis")
competitor_graph.add_edge("similarity_analysis", "gap_analysis")
competitor_graph.add_edge("gap_analysis", "competitive_gaps")
competitor_graph.add_edge("competitive_gaps", "competitive_content_intelligence")
competitor_graph.add_edge("competitive_content_intelligence", "competitor_intelligence")
competitor_graph.add_edge("competitor_intelligence", "recommendations")
competitor_graph.add_edge("recommendations", "generate_competitor_summary")
competitor_graph.add_edge("generate_competitor_summary", END)

competitor_graph_app = competitor_graph.compile()
