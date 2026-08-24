from langgraph.graph import END, START, StateGraph

from agents.contentrecommendation.node.AnalyzeCompetitorContentNode import (
    AnalyzeCompetitorContentNode,
)
from agents.contentrecommendation.node.AnalyzeSocialPerformanceNode import (
    AnalyzeSocialPerformanceNode,
)
from agents.contentrecommendation.node.DetectContentOpportunitiesNode import (
    DetectContentOpportunitiesNode,
)
from agents.contentrecommendation.node.GenerateContentCalendarNode import (
    GenerateContentCalendarNode,
)
from agents.contentrecommendation.node.GenerateContentIdeasNode import (
    GenerateContentIdeasNode,
)
from agents.contentrecommendation.node.GenerateContentStrategyNode import (
    GenerateContentStrategyNode,
)
from agents.contentrecommendation.node.GeneratePlatformStrategyNode import (
    GeneratePlatformStrategyNode,
)
from agents.contentrecommendation.pipeline_log import with_pipeline_log
from agents.contentrecommendation.state.contentstate import ContentState

content_graph = StateGraph(ContentState)
content_graph.add_node(
    "analyze_social_performance",
    with_pipeline_log("analyze_social_performance", AnalyzeSocialPerformanceNode),
)
content_graph.add_node(
    "analyze_competitor_content",
    with_pipeline_log("analyze_competitor_content", AnalyzeCompetitorContentNode),
)
content_graph.add_node(
    "detect_content_opportunities",
    with_pipeline_log("detect_content_opportunities", DetectContentOpportunitiesNode),
)
content_graph.add_node(
    "generate_content_strategy",
    with_pipeline_log("generate_content_strategy", GenerateContentStrategyNode),
)
content_graph.add_node(
    "generate_platform_strategy",
    with_pipeline_log("generate_platform_strategy", GeneratePlatformStrategyNode),
)
content_graph.add_node(
    "generate_content_ideas",
    with_pipeline_log("generate_content_ideas", GenerateContentIdeasNode),
)
content_graph.add_node(
    "generate_content_calendar",
    with_pipeline_log("generate_content_calendar", GenerateContentCalendarNode),
)

content_graph.add_edge(START, "analyze_social_performance")
content_graph.add_edge("analyze_social_performance", "analyze_competitor_content")
content_graph.add_edge("analyze_competitor_content", "detect_content_opportunities")
content_graph.add_edge("detect_content_opportunities", "generate_content_strategy")
content_graph.add_edge("generate_content_strategy", "generate_platform_strategy")
content_graph.add_edge("generate_platform_strategy", "generate_content_ideas")
content_graph.add_edge("generate_content_ideas", "generate_content_calendar")
content_graph.add_edge("generate_content_calendar", END)

content_recommendation_app = content_graph.compile()
