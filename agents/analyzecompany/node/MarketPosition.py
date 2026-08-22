"""Market position + positioning analysis from company DNA."""

from __future__ import annotations

from agents.analyzecompany.intelligence_context import _clip, clamp_score, intelligence_context
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


def _level(count: int, *, low: int, high: int) -> str:
    if count >= high:
        return "High"
    if count >= low:
        return "Medium"
    return "Low"


async def MarketPositionNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    ctx = intelligence_context(state)
    services = ctx["services"]
    flagship = ctx["flagship"]
    geo_blob = " ".join(ctx["geography"] + ctx["keywords"] + ctx["audience"]).lower()
    positioning = str(ctx.get("positioning") or "")
    vp = str(ctx.get("value_proposition") or "")

    ai_heavy = sum(1 for s in services + flagship if "ai" in s.lower() or "llm" in s.lower())
    category = "AI Software Engineering" if ai_heavy >= 2 or "ai" in positioning.lower() else (
        str(ctx.get("industry") or "Technology Services")
    )

    position = "AI-native engineering partner" if ai_heavy else _clip(positioning or category, 80)

    service_breadth = _level(len(services), low=6, high=12)
    specialization = "High" if len(flagship) <= 3 and len(services) <= 8 else (
        "Medium" if len(services) <= 16 else "Low"
    )
    geographic_focus = "GCC / MENA" if ("gcc" in geo_blob or "mena" in geo_blob) else (
        ctx.get("region") or "Global"
    )
    enterprise_focus = "High" if any(
        token in " ".join(ctx["audience"]).lower()
        for token in ("enterprise", "gcc", "mena", "cto")
    ) else "Medium"

    diff = 55.0
    clarity = 50.0
    if positioning:
        clarity += 12
        diff += 8
    if vp and vp.lower() != positioning.lower():
        clarity += 8
        diff += 6
    if ai_heavy:
        diff += 10
    if geographic_focus != "Global":
        diff += 6
        clarity += 4
    if len(services) > 14:
        clarity -= 10
        diff -= 6
    if not ctx["pain_points"]:
        clarity -= 5

    assessment = (
        "Strong technical breadth but positioning is broad."
        if service_breadth == "High" and specialization != "High"
        else "Focused positioning with clear category ownership."
        if specialization == "High"
        else "Solid market presence with room to sharpen specialization."
    )

    known = flagship[:5] or services[:5]
    unclear: list[str] = []
    if len(ctx["industries"]) != 1:
        unclear.append("Primary industry specialization")
    if not any("cto" in a.lower() or "leader" in a.lower() for a in ctx["audience"]):
        unclear.append("Specific buyer")
    if "roi" not in vp.lower() and "outcome" not in vp.lower() and "overcome" not in vp.lower():
        unclear.append("Unique business outcome")
    if not unclear:
        unclear.append("Proof of measurable outcomes")

    market = ctx.get("region") or "target"
    if "gcc" in geo_blob or "mena" in geo_blob:
        market = "GCC enterprises"
    recommended = (
        f"AI-native engineering partner for {market} modernizing operations with AI."
        if ai_heavy
        else f"Specialist technology partner for {market} buyers."
    )

    state["market_position"] = {
        "category": category,
        "position": position,
        "specialization": specialization,
        "service_breadth": service_breadth,
        "geographic_focus": str(geographic_focus),
        "enterprise_focus": enterprise_focus,
        "differentiation_strength": clamp_score(diff),
        "positioning_clarity": clamp_score(clarity),
        "assessment": assessment,
    }
    state["positioning_analysis"] = {
        "what_you_are_known_for": [s[:80] for s in known],
        "what_is_unclear": unclear[:4],
        "recommended_positioning": recommended,
    }

    log_event(
        "3_intelligence",
        "Market position assessed",
        category=category,
        specialization=specialization,
        clarity=clamp_score(clarity),
    )
    return state
