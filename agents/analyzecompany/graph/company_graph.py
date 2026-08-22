from langgraph.graph import END, START, StateGraph

from agents.analyzecompany.node.AnalyzeUserInsta import AnalyzeUserInstaNode
from agents.analyzecompany.node.AnalyzeUserLinkedIn import AnalyzeUserLinkedInNode
from agents.analyzecompany.node.DiigitalPresence import DigitalPresenceNode
from agents.analyzecompany.node.ExecutiveNode import ExecutiveNode
from agents.analyzecompany.node.GenerateCompanySummary import GenerateCompanySummaryNode
from agents.analyzecompany.node.GrowthOpportunities import GrowthOpportunitiesNode
from agents.analyzecompany.node.MarketPosition import MarketPositionNode
from agents.analyzecompany.node.Recommendations import RecommendationsNode
from agents.analyzecompany.node.Strengthandweekness import StrengthandweeknessNode
from agents.analyzecompany.node.UnderstandCompany import UnderstandCompanyNode
from agents.analyzecompany.pipeline_log import with_pipeline_log
from agents.analyzecompany.routing import (
    route_after_instagram,
    route_after_linkedin,
    route_after_website,
)
from agents.analyzecompany.state.companystate import AnalyzeCompanyState

company_graph = StateGraph(AnalyzeCompanyState)

# Phase 1 — Company DNA
company_graph.add_node("understand_company", with_pipeline_log("understand_company", UnderstandCompanyNode))
company_graph.add_node("analyze_user_instagram", with_pipeline_log("analyze_user_instagram", AnalyzeUserInstaNode))
company_graph.add_node("analyze_user_linkedin", with_pipeline_log("analyze_user_linkedin", AnalyzeUserLinkedInNode))
company_graph.add_node("generate_company_summary", with_pipeline_log("generate_company_summary", GenerateCompanySummaryNode))

# Phase 2 — Company intelligence
company_graph.add_node("digital_presence", with_pipeline_log("digital_presence", DigitalPresenceNode))
company_graph.add_node("market_position", with_pipeline_log("market_position", MarketPositionNode))
company_graph.add_node("executive_snapshot", with_pipeline_log("executive_snapshot", ExecutiveNode))
company_graph.add_node("strengths_weaknesses", with_pipeline_log("strengths_weaknesses", StrengthandweeknessNode))
company_graph.add_node("growth_opportunities", with_pipeline_log("growth_opportunities", GrowthOpportunitiesNode))
company_graph.add_node("recommendations", with_pipeline_log("recommendations", RecommendationsNode))

company_graph.add_edge(START, "understand_company")
company_graph.add_conditional_edges(
    "understand_company",
    route_after_website,
    {
        "analyze_user_instagram": "analyze_user_instagram",
        "analyze_user_linkedin": "analyze_user_linkedin",
        "generate_company_summary": "generate_company_summary",
    },
)
company_graph.add_conditional_edges(
    "analyze_user_instagram",
    route_after_instagram,
    {
        "analyze_user_linkedin": "analyze_user_linkedin",
        "generate_company_summary": "generate_company_summary",
    },
)
company_graph.add_conditional_edges(
    "analyze_user_linkedin",
    route_after_linkedin,
    {
        "generate_company_summary": "generate_company_summary",
    },
)

# DNA → intelligence funnel
company_graph.add_edge("generate_company_summary", "digital_presence")
company_graph.add_edge("digital_presence", "market_position")
company_graph.add_edge("market_position", "executive_snapshot")
company_graph.add_edge("executive_snapshot", "strengths_weaknesses")
company_graph.add_edge("strengths_weaknesses", "growth_opportunities")
company_graph.add_edge("growth_opportunities", "recommendations")
company_graph.add_edge("recommendations", END)

analyze_company_app = company_graph.compile()
