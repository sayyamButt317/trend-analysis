"""Executive snapshot from company DNA + digital presence."""

from __future__ import annotations

from agents.analyzecompany.intelligence_context import _clip, _list, clamp_score, intelligence_context
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


def _company_type(ctx: dict) -> str:
    services = " ".join(ctx["services"] + ctx["flagship"] + ctx["keywords"]).lower()
    industry = str(ctx.get("industry") or "").lower()
    if "ai" in services or "llm" in services or "genai" in services:
        return "B2B AI Engineering Partner"
    if "staff augmentation" in services or "resource" in services:
        return "B2B IT Services / Staff Augmentation"
    if industry:
        return f"B2B {ctx['industry']} Company"
    return "B2B Technology Services"


def _primary_market(ctx: dict) -> str:
    blob = " ".join(ctx["geography"] + ctx["keywords"] + ctx["audience"] + [str(ctx.get("positioning") or "")]).lower()
    bits: list[str] = []
    if "gcc" in blob:
        bits.append("GCC")
    if "mena" in blob:
        bits.append("MENA")
    if ctx.get("region") and str(ctx["region"]).lower() not in {"gcc", "mena"}:
        # Keep operating base separate from go-to-market.
        pass
    if bits:
        return " / ".join(bits)
    if ctx.get("region"):
        return str(ctx["region"])
    return "Global"


def _customers(ctx: dict) -> list[str]:
    audience = ctx["audience"][:4]
    if audience:
        # Normalize enterprise audience into buyer personas when generic.
        mapped: list[str] = []
        for item in audience:
            lower = item.lower()
            if "cto" in lower or " technol" in lower:
                mapped.append(item)
            elif "enterprise" in lower or "gcc" in lower or "mena" in lower:
                mapped.append(item)
            else:
                mapped.append(item)
        # Add role personas when audience is company-type only.
        if not any("cto" in x.lower() or "leader" in x.lower() for x in mapped):
            mapped.extend(
                [
                    "Enterprise CTOs",
                    "Digital Transformation Leaders",
                    "Operations Leaders",
                ]
            )
        return list(dict.fromkeys(mapped))[:5]
    return ["Enterprise CTOs", "Digital Transformation Leaders", "Operations Leaders"]


def _core_offering(ctx: dict) -> str:
    flagship = ctx["flagship"][:3]
    if flagship and any("ai" in s.lower() for s in flagship):
        return "AI-native software engineering and automation"
    if flagship:
        return _clip(", ".join(flagship), 120)
    return "Custom software and digital engineering services"


def _maturity(ctx: dict) -> str:
    followers = ctx.get("ig_followers") or 0
    services = len(ctx["services"])
    if followers >= 5000 or services >= 20:
        return "Scaling SME"
    if followers >= 500 or services >= 8:
        return "Growing SME"
    return "Early-stage / niche SME"


def _market_position_label(ctx: dict) -> str:
    positioning = _clip(ctx.get("positioning") or "", 120)
    if positioning:
        # Prefer short label from positioning.
        lower = positioning.lower()
        if "ai-native" in lower or "ai native" in lower:
            return "AI-native engineering partner"
        return positioning
    if any("ai" in s.lower() for s in ctx["flagship"] + ctx["services"]):
        return "AI-native engineering partner"
    return "Specialist technology partner"


async def ExecutiveNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    ctx = intelligence_context(state)
    digital = state.get("digital_presence") or {}
    overall = digital.get("overall_score")
    if overall is None:
        # Provisional score until digital node runs; executive may run before digital.
        overall = 55

    snapshot = {
        "company_type": _company_type(ctx),
        "business_model": (
            (ctx["pricing"][0] if ctx["pricing"] else None)
            or ctx.get("business_model")
            or "B2B services"
        ),
        "primary_market": _primary_market(ctx),
        "primary_customers": _customers(ctx),
        "core_offering": _core_offering(ctx),
        "market_position": _market_position_label(ctx),
        "business_maturity": _maturity(ctx),
        "overall_digital_presence_score": clamp_score(float(overall)),
    }
    state["executive_snapshot"] = snapshot
    log_event(
        "3_intelligence",
        "Executive snapshot ready",
        company=ctx["name"],
        type=snapshot["company_type"],
        market=snapshot["primary_market"],
    )
    return state
