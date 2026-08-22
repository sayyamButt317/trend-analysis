"""Recommended actions / action plan from insights."""

from __future__ import annotations

from agents.analyzecompany.intelligence_context import intelligence_context
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


async def RecommendationsNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    ctx = intelligence_context(state)
    opportunities = list(state.get("growth_opportunities") or [])
    positioning = state.get("positioning_analysis") or {}
    digital = state.get("digital_presence") or {}
    ig = digital.get("instagram") or {}

    actions: list[dict] = []

    recommended = positioning.get("recommended_positioning")
    if recommended:
        actions.append(
            {
                "priority": 1,
                "title": "Sharpen AI positioning",
                "category": "Positioning",
                "impact": "High",
                "effort": "Medium",
                "action": f"Position the company around {recommended.rstrip('.')}.",
            }
        )

    if any(o.get("area") == "Proof" for o in opportunities):
        actions.append(
            {
                "priority": 2,
                "title": "Build enterprise proof",
                "category": "Website",
                "impact": "High",
                "effort": "Medium",
                "action": "Add case studies with measurable business outcomes.",
            }
        )

    if any(o.get("area") == "Social Growth" for o in opportunities) or (
        ig.get("followers") is not None and int(ig.get("followers") or 0) < 1500
    ):
        actions.append(
            {
                "priority": 3,
                "title": "Increase social reach",
                "category": "Content",
                "impact": "Medium",
                "effort": "Low",
                "action": "Increase posting frequency and prioritize educational AI content.",
            }
        )

    if any(o.get("area") == "LinkedIn" for o in opportunities):
        actions.append(
            {
                "priority": len(actions) + 1,
                "title": "Activate LinkedIn intelligence",
                "category": "LinkedIn",
                "impact": "Medium",
                "effort": "Low",
                "action": "Publish weekly B2B posts and enable LinkedIn analysis on the next run.",
            }
        )

    # Fill from remaining high-priority opportunities (avoid duplicate actions).
    existing_actions = {str(a.get("action") or "").strip().lower() for a in actions}
    existing_categories = {str(a.get("category") or "").strip().lower() for a in actions}
    for item in opportunities:
        if len(actions) >= 5:
            break
        area = str(item.get("area") or "Opportunity")
        action_text = str(item.get("action") or "").strip()
        if action_text.lower() in existing_actions:
            continue
        if area.lower() in existing_categories or area.lower() in {
            "social growth",
            "positioning",
            "proof",
        }:
            # Already covered by primary actions above.
            if area.lower() in {"social growth", "positioning", "proof"}:
                continue
        actions.append(
            {
                "priority": len(actions) + 1,
                "title": f"Improve {area.lower()}",
                "category": area,
                "impact": "High" if item.get("priority") == "HIGH" else "Medium",
                "effort": "Medium",
                "action": action_text or "Prioritize this growth opportunity.",
            }
        )
        existing_actions.add(action_text.lower())
        existing_categories.add(area.lower())

    # Re-number priorities sequentially.
    for idx, action in enumerate(actions, start=1):
        action["priority"] = idx

    state["recommended_actions"] = actions[:5]
    log_event(
        "3_intelligence",
        "Recommendations ready",
        actions=len(state["recommended_actions"]),
        company=ctx["name"],
    )
    return state
