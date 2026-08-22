"""Digital presence scoring for website / Instagram / LinkedIn."""

from __future__ import annotations

from agents.analyzecompany.intelligence_context import clamp_score, intelligence_context
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


def _website_block(ctx: dict) -> dict:
    if not ctx["website_crawled"]:
        return {
            "score": None,
            "status": "Not crawled",
            "strengths": [],
            "weaknesses": ["Website not analyzed"],
        }

    score = 55.0
    strengths: list[str] = []
    weaknesses: list[str] = []

    if ctx["services"]:
        score += 12
        strengths.append("Clear service offering")
    else:
        weaknesses.append("Service offering unclear on site")

    if any("ai" in s.lower() for s in ctx["services"] + ctx["keywords"] + ctx["flagship"]):
        score += 8
        strengths.append("AI positioning")

    if ctx.get("positioning"):
        score += 6
    else:
        weaknesses.append("Weak differentiation")
        score -= 4

    if ctx["technologies"]:
        score += 5

    if len(ctx["services"]) > 14:
        weaknesses.append("Broad catalog may dilute focus")
        score -= 4

    # Proof / outcomes signal from pain points & case-like keywords.
    proof_blob = " ".join(ctx["keywords"] + [str(ctx.get("value_proposition") or "")]).lower()
    if any(token in proof_blob for token in ("case study", "roi", "outcome", "measurable")):
        score += 6
        strengths.append("Outcome-oriented messaging")
    else:
        weaknesses.append("Limited proof of outcomes")
        score -= 5

    if not strengths:
        strengths.append("Website presence detected")
    if not weaknesses:
        weaknesses.append("Differentiation can be sharpened")

    return {
        "score": clamp_score(score),
        "strengths": strengths[:4],
        "weaknesses": weaknesses[:4],
    }


def _instagram_block(ctx: dict) -> dict:
    if not ctx["ig_analyzed"]:
        return {
            "score": None,
            "followers": None,
            "engagement_rate": None,
            "content_strength": None,
            "audience_strength": None,
            "status": "Not analyzed",
        }

    followers = ctx.get("ig_followers") or 0
    eng = ctx.get("ig_engagement")

    # Audience strength: 357 followers → low 30s.
    if followers >= 10000:
        audience = 80
    elif followers >= 2000:
        audience = 62
    elif followers >= 800:
        audience = 48
    elif followers >= 300:
        audience = 31
    else:
        audience = 20

    # Content / engagement strength.
    content = 45
    if eng is not None:
        if eng >= 5:
            content = 70
        elif eng >= 3:
            content = 58
        elif eng >= 1.5:
            content = 48
        else:
            content = 35
    if ctx["ig_themes"] or ctx["ig_categories"]:
        content = min(100, content + 4)

    overall = clamp_score(audience * 0.45 + content * 0.55)
    return {
        "score": overall,
        "followers": followers or None,
        "engagement_rate": round(float(eng), 2) if eng is not None else None,
        "content_strength": clamp_score(content),
        "audience_strength": clamp_score(audience),
    }


def _linkedin_block(ctx: dict) -> dict:
    if not ctx["li_analyzed"]:
        return {"score": None, "status": "Not analyzed"}

    score = 50.0
    if ctx["li_themes"]:
        score += 15
    if ctx["li_hiring"]:
        score += 5
    return {"score": clamp_score(score), "status": "Analyzed"}


async def DigitalPresenceNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    ctx = intelligence_context(state)
    website = _website_block(ctx)
    instagram = _instagram_block(ctx)
    linkedin = _linkedin_block(ctx)

    scores: list[float] = []
    weights: list[float] = []
    if website.get("score") is not None:
        scores.append(float(website["score"]))
        weights.append(0.45)
    if instagram.get("score") is not None:
        scores.append(float(instagram["score"]))
        weights.append(0.35)
    if linkedin.get("score") is not None:
        scores.append(float(linkedin["score"]))
        weights.append(0.20)

    if scores and weights:
        # Renormalize weights for missing channels.
        total_w = sum(weights)
        overall = sum(s * (w / total_w) for s, w in zip(scores, weights))
    else:
        overall = 40

    presence = {
        "overall_score": clamp_score(overall),
        "website": website,
        "instagram": instagram,
        "linkedin": linkedin,
    }
    state["digital_presence"] = presence

    # Keep executive snapshot in sync if it already ran.
    executive = dict(state.get("executive_snapshot") or {})
    if executive:
        executive["overall_digital_presence_score"] = presence["overall_score"]
        state["executive_snapshot"] = executive

    log_event(
        "3_intelligence",
        "Digital presence scored",
        overall=presence["overall_score"],
        website=website.get("score"),
        instagram=instagram.get("score"),
        linkedin=linkedin.get("status") or linkedin.get("score"),
    )
    return state
