"""Strengths and weaknesses from DNA + digital signals."""

from __future__ import annotations

from agents.analyzecompany.intelligence_context import intelligence_context
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


async def StrengthandweeknessNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    ctx = intelligence_context(state)
    digital = state.get("digital_presence") or {}
    market = state.get("market_position") or {}
    ig = digital.get("instagram") or {}
    li = digital.get("linkedin") or {}
    web = digital.get("website") or {}

    strengths: list[str] = []
    weaknesses: list[str] = []

    if any("ai" in s.lower() or "llm" in s.lower() for s in ctx["services"] + ctx["flagship"]):
        strengths.append("Strong AI/LLM positioning")
    if len(ctx["services"]) >= 6 or len(ctx["technologies"]) >= 6:
        strengths.append("Broad engineering capability")
    geo = " ".join(ctx["geography"] + ctx["keywords"] + ctx["audience"]).lower()
    if "gcc" in geo or "mena" in geo:
        strengths.append("Clear GCC/MENA focus")
    if any("enterprise" in a.lower() for a in ctx["audience"]) or len(ctx["services"]) >= 5:
        strengths.append("Multiple enterprise-oriented services")

    followers = ig.get("followers")
    eng = ig.get("engagement_rate")
    if followers is not None and eng is not None and eng >= 3 and followers < 2000:
        strengths.append("Good Instagram engagement relative to audience size")
    elif eng is not None and eng >= 5:
        strengths.append("Strong Instagram engagement rate")

    for item in (web.get("strengths") or [])[:2]:
        if item not in strengths and "ai positioning" not in item.lower():
            strengths.append(item)

    if li.get("status") == "Not analyzed" or li.get("score") is None:
        weaknesses.append("LinkedIn intelligence unavailable")
    if followers is not None and followers < 1000:
        weaknesses.append("Very small Instagram audience")
    if market.get("service_breadth") == "High" and market.get("specialization") != "High":
        weaknesses.append("Positioning is broad rather than highly specialized")
    if len(ctx["services"]) > 12:
        weaknesses.append("Too many services dilute the core proposition")
    if any("proof" in str(w).lower() or "outcome" in str(w).lower() for w in (web.get("weaknesses") or [])):
        weaknesses.append("Limited visible proof/case-study signals")
    elif "Limited proof of outcomes" in (web.get("weaknesses") or []):
        weaknesses.append("Limited visible proof/case-study signals")
    else:
        proof_blob = " ".join(ctx["keywords"] + [str(ctx.get("value_proposition") or "")]).lower()
        if not any(t in proof_blob for t in ("case", "roi", "outcome", "measurable")):
            weaknesses.append("Limited visible proof/case-study signals")

    # Deduplicate while preserving order.
    strengths = list(dict.fromkeys(strengths))[:8]
    weaknesses = list(dict.fromkeys(weaknesses))[:8]
    if not strengths:
        strengths.append("Foundational company DNA captured from available channels")
    if not weaknesses:
        weaknesses.append("Limited multi-channel evidence for deeper competitive scoring")

    state["strengths_and_weaknesses"] = {
        "strengths": strengths,
        "weaknesses": weaknesses,
    }
    log_event(
        "3_intelligence",
        "Strengths & weaknesses ready",
        strengths=len(strengths),
        weaknesses=len(weaknesses),
    )
    return state
