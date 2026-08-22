from typing import Any
from service.Competitor.competitor_proposer import MIN_COMPETITORS
from service.Competitor.openai_client import chat_completion_json, resolve_openai_model
from config.credential_config import config
from prompts.competitor_proposal import SYSTEM_PROMPT
from service.Competitor.competitor_proposer import _build_user_dna_blob, normalize_proposed_competitors
import logging

logger = logging.getLogger(__name__)

class CompetitorProposerService:

    async def propose(
    self,
    *,
    company: dict[str, Any],
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any],
    company_signals: dict[str, Any] | None = None,
    discovery_features: dict[str, Any] | None = None,
    instagram_analysis: dict[str, Any] | None = None,
    linkedin_analysis: dict[str, Any] | None = None,
    website_intelligence: dict[str, Any] | None = None,
    region: str,
    limit: int = MIN_COMPETITORS,
    hints: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not (config.OPENAI_API_KEY or "").strip():
            raise ValueError("OPENAI_API_KEY is not configured")

        target = max(1, int(limit or MIN_COMPETITORS))
        dna = _build_user_dna_blob(
        company=company,
        company_profile=company_profile,
        company_analysis=company_analysis,
        company_signals=company_signals,
        discovery_features=discovery_features,
        instagram_analysis=instagram_analysis,
        linkedin_analysis=linkedin_analysis,
        website_intelligence=website_intelligence,
)
        own_name = (dna.get("name") or "").strip().lower()
        own_ig = (dna.get("instagram_username") or "").strip().lstrip("@").lower()
        services = dna.get("services") or []
        technologies = dna.get("technologies") or []
        keywords = dna.get("keywords") or []

        instagram_topics = dna.get("instagram_topics") or []
        linkedin_topics = dna.get("linkedin_topics") or []

        website_services = dna.get("website_services") or []
        target_audience = dna.get("target_audience") or []
        company_size = dna.get("linkedin_company_size")
        is_hiring = dna.get("linkedin_is_hiring")

        user_prompt = f"""
You are identifying REAL competitors for a company.Think carefully before selecting competitors.

Internally perform these steps:

STEP 1
Understand exactly what this company sells.

STEP 2
Identify its primary customer.

STEP 3
Identify secondary customer segments.

STEP 4
Determine the company's business model.

Examples:
• Software Company
• SaaS
• Marketing Agency
• AI Consultancy
• Cloud Consultancy
• Healthcare
• Fintech
• Real Estate
• E-commerce
• Manufacturing
• Recruitment

STEP 5
Determine company size.

Examples:
Startup
SME
Mid Market
Enterprise

STEP 6
Determine geographic market.

Examples:
Pakistan
Middle East
UAE
Saudi Arabia
Global

STEP 7
Determine service overlap.

Competitors should share at least
70% of services.

STEP 8
Determine customer overlap.

Competitors should target similar customers.

STEP 9
Determine positioning overlap.

Compare:

• pricing
• expertise
• technologies
• industry focus
• messaging
• specialization

STEP 10
Score every candidate.

Score based on

Service similarity 35%

Customer similarity 25%

Industry overlap 15%

Region overlap 10%

Technology overlap 10%

Social presence 5%

Only keep competitors with
Similarity Score >= 70.

If fewer than requested exist,
return only authentic competitors.
Never invent companies.
Never return companies that only have similar keywords.
Think carefully before producing the final JSON.

Only return companies that genuinely compete for the SAME customers.

STEP 11

Before selecting a competitor, verify that:

- The company currently exists.
- The company actively provides these services.
- The company operates in the specified region.
- The website clearly describes similar offerings.
- At least one public source confirms the company.

Reject companies if any of these checks fail.

----------------------------------------------------
COMPANY
----------------------------------------------------

Name:
{dna.get("name")}

Region:
{region}

Business Summary:
{dna.get("summary")}

Positioning:
{dna.get("positioning")}

Value Proposition:
{dna.get("value_proposition")}

----------------------------------------------------
SERVICES
----------------------------------------------------

Primary Services

{services}

Website Services

{website_services}

----------------------------------------------------
TECHNOLOGY
----------------------------------------------------

Technologies

{technologies}

----------------------------------------------------
TARGET AUDIENCE
----------------------------------------------------

{target_audience}

----------------------------------------------------
CONTENT STRATEGY
----------------------------------------------------

Instagram Topics

{instagram_topics}

LinkedIn Topics

{linkedin_topics}

Keywords

{keywords}

----------------------------------------------------
SOCIAL SIGNALS
----------------------------------------------------

Instagram Username

{dna.get("instagram_username")}

LinkedIn Company Size

{company_size}

Currently Hiring

{is_hiring}

----------------------------------------------------
RULES
----------------------------------------------------

Return ONLY companies that satisfy ALL conditions:

1.Offer very similar services.
2.Target the same customer type.
3.Operate in the same region.
4.Similar company size.
5.Compete for the same projects.
6.Not marketplaces.
7.Not agencies unless this company is an agency.
8.Not software vendors unless this company sells software.
9.Not partners.
10.Not technology providers.
11.Not clients.
12.Not investors.
13.Not media companies.
14.Must have an active business website.
15.Must have either Instagram OR LinkedIn.
16.Must currently be operating.
17.Avoid multinational giants if the user company is SME.
18.Prefer companies with similar employee count.
19.Prefer companies with similar service portfolio.
20.Return the BEST {limit} competitors.
----------------------------------------------------
FOR EACH COMPETITOR RETURN
Company Name
Website
Why they compete
Similarity Score (0-100)
Services
Country
City
Instagram Username
LinkedIn URL
Confidence (0-1)
----------------------------------------------------
Return ONLY JSON.

"""
        data = await chat_completion_json(
            model=resolve_openai_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            timeout=120,
        )
        raw = data.get("competitors") or []
        if not isinstance(raw, list):
            raw = []

        competitors = normalize_proposed_competitors(
            raw,
            exclude_names={own_name} if own_name else set(),
            exclude_instagram={own_ig} if own_ig else set(),
            limit=max(target + 5, target),
        )
        meta = {
            "matching_mode": "openai_proposal",
            "discovery_source": "openai_competitor_proposal",
            "competitor_target": target,
            "openai_returned": len(raw),
            "openai_accepted": len(competitors),
            "reasoning": data.get("reasoning"),
        }
        logger.info(
            "OpenAI proposed %s competitors (accepted %s) for region=%s",
            len(raw),
            len(competitors),
            region,
        )
        return competitors[:target], meta


