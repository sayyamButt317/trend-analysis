from __future__ import annotations
import logging
from typing import Any
from agents.contentrecommendation.state.contentstate import ContentState
from service.Competitor.openai_client import (
    chat_completion_json,
    resolve_openai_model,
)

logger = logging.getLogger(__name__)


def _build_opportunity_input(
    platform: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    company_dna = data.get("company_dna") or {}
    company_analysis = data.get("company_analysis") or {}
    social_performance = data.get("social_performance") or {}
    competitor_analysis = data.get("competitor_analysis") or {}
    competitor_content = data.get("competitor_content") or {}

    return {
        "platform": platform,
        "company_dna": {
            "services": company_dna.get("services") or [],
            "technologies": company_dna.get("technologies") or [],
            "target_audience": company_dna.get("target_audience") or [],
            "positioning": company_dna.get("positioning"),
            "value_proposition": company_dna.get("value_proposition"),
            "keywords": company_dna.get("keywords") or [],
        },
        "company_analysis": company_analysis,
        "social_performance": social_performance.get(platform) or {},
        "competitor_analysis": competitor_analysis,
        "competitor_content": competitor_content,
    }


def _build_prompt(
    platform: str,
    analysis_input: dict[str, Any],
) -> str:
    return f"""
You are a senior social media strategist.
Your job is to identify CONTENT OPPORTUNITIES for a company.
You are NOT generating random content ideas.
You must identify topics where the company has a strategic advantage or
where there is a clear market/content gap.
PLATFORM
{platform}
==================================================
COMPANY DNA
==================================================
{analysis_input["company_dna"]}
==================================================
COMPANY ANALYSIS
==================================================
{analysis_input["company_analysis"]}
==================================================
CURRENT SOCIAL PERFORMANCE
==================================================
{analysis_input["social_performance"]}
==================================================
COMPETITOR ANALYSIS
=================================================

{analysis_input["competitor_analysis"]}
==================================================
COMPETITOR CONTENT
==================================================
{analysis_input["competitor_content"]}
==================================================
ANALYSIS FRAMEWORK
==================================================
Identify opportunities using these signals:
1. COMPANY EXPERTISE
Does the company have strong expertise, services,
technologies or case studies related to the topic?
2. AUDIENCE RELEVANCE
Does the topic matter to the company's target customers?
3. COMPETITOR ACTIVITY
Are competitors actively talking about this topic?
4. COMPETITOR ENGAGEMENT
Are competitor posts about this topic generating
strong engagement?
5. CONTENT GAP
Are competitors NOT covering an important topic
that the company is capable of owning?
6. COMPANY PERFORMANCE
Has the company already demonstrated strong performance
around this topic?
7. PLATFORM FIT
Does this topic work particularly well on the selected platform?
8. BUSINESS VALUE
Can this topic help generate:
- awareness
- authority
- leads
- trust
- consideration
- conversions
==================================================
OPPORTUNITY TYPES
==================================================
You may identify opportunities such as:
COMPETITOR_VALIDATED
Competitors are getting strong engagement from this topic
and the company has relevant expertise.
CONTENT_GAP
Competitors have weak coverage but the company has strong
expertise and business relevance.
AUTHORITY
The company has unique expertise that competitors cannot
easily replicate.
PERFORMANCE
The company's own content performs strongly around this topic.
COMMERCIAL
The topic directly connects to a service or business goal.
TREND
The topic is gaining market attention and aligns with
company expertise.
==================================================
PRIORITY SCORE
==================================================
Calculate priority from 0-100.
Consider:
Company expertise        20%
Audience relevance       20%
Business value           20%
Competitor signal        15%
Content gap              10%
Platform fit             10%
Existing performance      5%
Do NOT give every opportunity a high score.
90-100 = exceptional opportunity
80-89  = strong opportunity
70-79  = good opportunity
60-69  = moderate opportunity
below 60 = do not recommend
==================================================
IMPORTANT RULES
==================================================
1. Do not invent company expertise.
2. Do not invent competitor activity.
3. Do not claim high engagement unless the provided data
   supports it.
4. Do not recommend topics unrelated to the company.
5. Do not simply repeat company keywords.
6. A competitor talking about a topic does NOT automatically
   make it an opportunity.
7. Prioritize topics where the company has a reason to win.
8. Prefer specific topics over generic topics.
BAD:
"AI"
GOOD:
"AI agents for automating enterprise workflows"
BAD:
"Software development"
GOOD:
"How to modernize legacy enterprise systems with AI"
9. Keep opportunities actionable.
10. Return only the strongest opportunities.
Return maximum 10 opportunities.
==================================================
OUTPUT
==================================================
Return ONLY valid JSON.
Schema:
{{
    "opportunities": [
        {{
            "topic": "specific content topic",
            "opportunity_type":
                "COMPETITOR_VALIDATED | CONTENT_GAP | AUTHORITY | PERFORMANCE | COMMERCIAL | TREND",
            "reason":
                "Clear explanation based on the supplied data",
            "priority": 92,
            "business_value":
                "awareness | authority | leads | trust | consideration | conversion",
            "recommended_formats": [
                "LinkedIn carousel",
                "LinkedIn document"
            ],
            "recommended_angles": [
                "specific angle 1",
                "specific angle 2"
            ],
            "evidence": {{
                "company_expertise": true,
                "audience_relevance": true,
                "competitor_activity": true,
                "competitor_engagement": true,
                "content_gap": false,
                "existing_performance": false
            }}
        }}
    ]
}}
"""


async def detect_content_opportunities(
    social_media_platform: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    platform = social_media_platform.strip().lower()
    analysis_input = _build_opportunity_input(platform, data)
    prompt = _build_prompt(platform, analysis_input)

    try:
        response = await chat_completion_json(
            model=resolve_openai_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior social media strategist "
                        "specialized in competitive content intelligence. "
                        "Only use evidence provided in the input."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            timeout=120,
        )
    except Exception as exc:
        logger.warning(
            "OpenAI opportunity detection failed for %s (%s); using deterministic fallback",
            platform,
            exc,
        )
        from service.ContentRecommendation.builder import build_content_opportunities

        fallback = build_content_opportunities(
            company=data.get("company") or {},
            company_dna=data.get("company_dna") or {},
            social_performance=data.get("social_performance") or {},
            competitor_content=data.get("competitor_content") or {},
            content_intelligence=data.get("content_intelligence") or {},
            business_goals=data.get("business_goals") or [],
        )
        return {
            "platform": platform,
            "opportunities": list(fallback.get("opportunities") or [])[:10],
            "fallback": True,
            "fallback_reason": str(exc)[:200],
        }

    opportunities = response.get("opportunities") or []
    if not isinstance(opportunities, list):
        opportunities = []

    normalized = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict):
            continue
        priority = opportunity.get("priority", 0)
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            priority = 0
        priority = max(0, min(priority, 100))
        normalized.append(
            {
                "topic": str(opportunity.get("topic") or "").strip(),
                "opportunity_type": opportunity.get("opportunity_type") or "CONTENT_GAP",
                "reason": str(opportunity.get("reason") or "").strip(),
                "priority": priority,
                "business_value": opportunity.get("business_value") or "awareness",
                "recommended_formats": opportunity.get("recommended_formats") or [],
                "recommended_angles": opportunity.get("recommended_angles") or [],
                "evidence": opportunity.get("evidence") or {},
            }
        )

    normalized = [row for row in normalized if row["topic"]]
    normalized.sort(key=lambda item: item["priority"], reverse=True)
    return {"platform": platform, "opportunities": normalized[:10]}


async def DetectContentOpportunitiesNode(state: ContentState) -> ContentState:
    try:
        config = state.get("config") or {}
        company = state.get("company") or config.get("company") or {}
        company_dna = state.get("company_dna") or config.get("company_dna") or {}
        data = {
            "company": company,
            "company_dna": company_dna,
            "company_analysis": state.get("company_analysis") or {},
            "social_performance": state.get("social_performance") or {},
            "competitor_analysis": state.get("competitor_analysis") or {},
            "competitor_content": state.get("competitor_content") or {},
            "content_intelligence": (
                state.get("content_intelligence_input")
                or config.get("content_intelligence")
                or {}
            ),
            "business_goals": state.get("business_goals") or config.get("business_goals") or [],
        }
        platforms = state.get("platforms") or ["instagram", "linkedin"]
        all_opportunities: dict[str, Any] = {}
        used_fallback = False
        for platform in platforms:
            result = await detect_content_opportunities(
                social_media_platform=platform,
                data=data,
            )
            all_opportunities[platform] = result
            if result.get("fallback"):
                used_fallback = True

        state["content_opportunities"] = all_opportunities
        state.setdefault("logs", []).append(
            "Content opportunities detected"
            + (" (fallback after OpenAI connect failure)." if used_fallback else ".")
        )
        return state
    except Exception as exc:
        logger.exception("Content opportunity detection failed")
        state["content_opportunities"] = {}
        state.setdefault("logs", []).append(
            f"Content opportunity detection skipped: {exc}"
        )
        return state
