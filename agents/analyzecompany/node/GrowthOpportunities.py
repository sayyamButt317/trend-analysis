"""Growth opportunities derived from strengths/weaknesses + channel gaps."""

from __future__ import annotations

from agents.analyzecompany.intelligence_context import intelligence_context
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


async def GrowthOpportunitiesNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    ctx = intelligence_context(state)
    sw = state.get("strengths_and_weaknesses") or {}
    digital = state.get("digital_presence") or {}
    market = state.get("market_position") or {}
    positioning = state.get("positioning_analysis") or {}
    ig = digital.get("instagram") or {}
    li = digital.get("linkedin") or {}

    opportunities: list[dict] = []

    if market.get("service_breadth") == "High" or any(
        "broad" in w.lower() or "dilute" in w.lower() for w in (sw.get("weaknesses") or [])
    ):
        opportunities.append(
            {
                "priority": "HIGH",
                "area": "Positioning",
                "finding": "The company promotes a broad range of engineering services.",
                "impact": "Potentially weakens differentiation.",
                "action": "Lead with AI-native engineering and automation instead of presenting all services equally.",
            }
        )

    followers = ig.get("followers")
    eng = ig.get("engagement_rate")
    if followers is not None and followers < 1500 and eng is not None and eng >= 2:
        opportunities.append(
            {
                "priority": "HIGH",
                "area": "Social Growth",
                "finding": "Instagram audience is small despite relatively strong engagement.",
                "impact": "Low reach limits brand discovery.",
                "action": "Increase publishing frequency and replicate high-engagement formats.",
            }
        )
    elif ig.get("score") is None:
        opportunities.append(
            {
                "priority": "MEDIUM",
                "area": "Social Growth",
                "finding": "Instagram presence was not analyzed.",
                "impact": "Missing social discovery channel insights.",
                "action": "Connect Instagram and publish educational content for target buyers.",
            }
        )

    if any("proof" in w.lower() or "case" in w.lower() for w in (sw.get("weaknesses") or [])):
        opportunities.append(
            {
                "priority": "MEDIUM",
                "area": "Proof",
                "finding": "Multiple technical capabilities are listed but outcome-based proof is limited.",
                "impact": "Enterprise buyers may have difficulty evaluating credibility.",
                "action": "Publish case studies showing measurable business outcomes.",
            }
        )

    if li.get("status") == "Not analyzed" or li.get("score") is None:
        opportunities.append(
            {
                "priority": "MEDIUM",
                "area": "LinkedIn",
                "finding": "LinkedIn intelligence is unavailable for this company.",
                "impact": "Weak visibility into B2B content and hiring signals.",
                "action": "Analyze LinkedIn company page content and publish buyer-facing thought leadership.",
            }
        )

    unclear = positioning.get("what_is_unclear") or []
    if "Specific buyer" in unclear:
        opportunities.append(
            {
                "priority": "MEDIUM",
                "area": "Buyer Clarity",
                "finding": "Primary buyer persona is not sharply defined in public messaging.",
                "impact": "Sales and content may speak to too many audiences at once.",
                "action": "Anchor messaging to one primary buyer (e.g. Enterprise CTOs in GCC).",
            }
        )

    # Priority sort: HIGH first.
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    opportunities.sort(key=lambda item: rank.get(str(item.get("priority") or "LOW"), 9))
    state["growth_opportunities"] = opportunities[:6]

    log_event(
        "3_intelligence",
        "Growth opportunities ready",
        count=len(state["growth_opportunities"]),
        company=ctx["name"],
    )
    return state
