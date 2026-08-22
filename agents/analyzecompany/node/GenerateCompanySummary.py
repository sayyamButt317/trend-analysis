from typing import Any
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


_MAX_SUMMARY_CHARS = 4500


def _is_junk(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or len(text) > 120:
        return True
    lower = text.lower()
    return (
        "mostly carousel" in lower
        or "focused on" in lower
        or ("%" in text and "carousel" in lower)
        or lower.startswith("http")
    )


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                label = (
                    item.get("name")
                    or item.get("label")
                    or item.get("theme")
                    or item.get("category")
                    or item.get("type")
                    or item.get("service")
                    or item.get("technology")
                )
                text = str(label or "").strip()
            else:
                text = str(item or "").strip()
            if text and not _is_junk(text) and text not in out:
                out.append(text)
        return out
    if isinstance(value, str) and value.strip() and not _is_junk(value):
        return [value.strip()]
    return []


def _join(values: list[str] | None, *, limit: int = 20) -> str:
    items = [str(v).strip() for v in (values or []) if str(v).strip() and not _is_junk(v)]
    return ", ".join(items[:limit]) if items else ""


def _clip(text: Any, limit: int) -> str:
    value = " ".join(str(text or "").split()).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _paragraph(*parts: str) -> str:
    cleaned = [p.strip() for p in parts if p and str(p).strip()]
    return " ".join(cleaned)


def _section(title: str, body: str | list[str]) -> str:
    if isinstance(body, list):
        lines = [line for line in body if line and str(line).strip()]
        if not lines:
            return ""
        return f"## {title}\n" + "\n".join(f"- {line}" for line in lines)
    text = str(body or "").strip()
    if not text:
        return ""
    return f"## {title}\n{text}"


def _merge_unique(*groups: list[str], limit: int = 30) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if _is_junk(item):
                continue
            key = item.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item.strip())
            if len(out) >= limit:
                return out
    return out


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _same_message(a: Any, b: Any) -> bool:
    left = _norm_text(a).lower()
    right = _norm_text(b).lower()
    return bool(left and right and left == right)


def _build_value_proposition(
    *,
    name: str | None,
    services: list[str],
    audience: list[str],
    industries: list[str],
    geography: list[str],
    pain_points: list[str],
    positioning: str | None,
    existing_vp: str | None = None,
) -> str | None:
    existing = _norm_text(existing_vp)
    position = _norm_text(positioning)
    if existing and not _same_message(existing, position):
        return existing

    offer = _join(services[:3], limit=3) or "specialist engineering"
    buyer = _join(audience[:2], limit=2) or _join(industries[:2], limit=2) or "enterprise buyers"
    geo = _join(geography[:2], limit=2)
    top_pain = (pain_points[0] if pain_points else "").strip()
    if top_pain.lower().startswith("solve for:"):
        top_pain = top_pain.split(":", 1)[1].strip()

    parts = [
        f"Helps {buyer}",
        f"ship {_clip(offer, 120)}" if offer else "",
        f"in {geo}" if geo else "",
    ]
    core = " ".join(p for p in parts if p).strip()
    if top_pain:
        return _clip(f"{core} so they can overcome {top_pain[0].lower() + top_pain[1:]}", 320)
    if name:
        return _clip(f"{core} with production-ready delivery and measurable business outcomes", 320)
    return _clip(core, 320) or None


def _infer_pain_points(
    *,
    services: list[str],
    audience: list[str],
    industries: list[str],
    positioning: str | None,
    value_prop: str | None,
) -> list[str]:
    """Derive buyer pains from what the company sells when explicit pains are missing."""
    blob = " ".join(
        [
            " ".join(services),
            " ".join(audience),
            " ".join(industries),
            positioning or "",
            value_prop or "",
        ]
    ).lower()
    inferred: list[str] = []

    def add(label: str, *needles: str) -> None:
        if any(n in blob for n in needles) and label not in inferred:
            inferred.append(label)

    add("Slow or manual operations that need automation", "automation", "n8n", "workflow", "rpa")
    add("Legacy systems that are hard to modernize or migrate", "migration", "legacy", "modernization", "cloud")
    add("Need for AI/LLM capabilities without building in-house", "ai", "llm", "genai", "machine learning")
    add("Shortage of skilled engineers / need for staff augmentation", "staff augmentation", "dedicated team", "resource")
    add("Pressure to ship products faster with reliable engineering", "web application", "mobile", "product development", "mvp")
    add("Security, compliance, and governance risk", "security", "compliance", "governance", "cyber")
    add("Fragmented customer or operational data", "data", "analytics", "integration", "platform")
    add("Difficulty competing digitally in regulated or regional markets", "fintech", "healthtech", "gcc", "mena")

    if not inferred and services:
        inferred.append(f"Buyers struggling to execute on {_join(services[:3], limit=3)} without a specialist partner")
    return inferred[:8]


def _pains_from_social_signals(
    *,
    ig_themes: list[str],
    ig_categories: list[str],
    ig_bio: str | None,
    li_themes: list[str],
    li_specialties: list[str],
) -> list[str]:

    blob = " ".join(
        [
            " ".join(ig_themes),
            " ".join(ig_categories),
            ig_bio or "",
            " ".join(li_themes),
            " ".join(li_specialties),
        ]
    ).lower()
    found: list[str] = []

    def add(label: str, *needles: str) -> None:
        if any(n in blob for n in needles) and label not in found:
            found.append(label)

    add("Buyers need clearer product / service proof before choosing a vendor", "product", "services", "case study", "client")
    add("Employer-brand and talent attraction pressure", "hiring", "culture", "team", "career", "jobs")
    add("Need for thought-leadership / trust in complex B2B purchases", "thought", "leadership", "insight", "industry")
    add("Demand for automation and AI-enabled outcomes", "automation", "ai", "llm", "digital transformation")
    add("Need for reliable delivery partners in competitive markets", "delivery", "engineering", "development", "devops")
    return found[:6]


def _website_has_dna(website: dict[str, Any], company: dict[str, Any]) -> bool:
    if website.get("technologies") or website.get("services") or website.get("business_model"):
        return True
    if website.get("summary") or website.get("description") or website.get("industries"):
        return True
    if company.get("website") and (
        company.get("technologies") or company.get("services") or company.get("business_model")
    ):
        return True
    return bool(website.get("url") or company.get("website"))


def _prefer_website_then_linkedin(
    *,
    website_values: list[str],
    linkedin_values: list[str],
    website_available: bool,
    limit: int = 30,
) -> list[str]:

    site = [v for v in website_values if v and not _is_junk(v)]
    if website_available and site:
        return _merge_unique(site, limit=limit)
    linked = [v for v in linkedin_values if v and not _is_junk(v)]
    if linked:
        return _merge_unique(linked, limit=limit)
    return _merge_unique(site, limit=limit)


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, str) and _is_junk(value):
            continue
        return value
    return None


def _marketplace_line(brief: dict[str, Any]) -> str:
    bits: list[str] = []
    if brief.get("business_model"):
        bits.append(str(brief["business_model"]))
    industries = _join(brief.get("industries_targeted") or [], limit=6)
    if industries:
        bits.append(f"serving {industries}")
    geo = _join(brief.get("geography") or [], limit=5)
    if geo:
        bits.append(f"with geographic focus on {geo}")
    pricing = _join(brief.get("pricing_signals") or [], limit=4)
    if pricing:
        bits.append(f"commercial model signals: {pricing}")
    if not bits:
        return ""
    return _paragraph("Marketplace:", "; ".join(bits) + ".")


def _build_impactful_summary_text(
    *,
    company: dict[str, Any],
    config: dict[str, Any],
    brief: dict[str, Any],
    website: dict[str, Any],
    dna: dict[str, Any],
) -> str:

    name = brief.get("name") or company.get("name") or "Company"
    industry = brief.get("industry")
    if industry and _is_junk(industry):
        industry = None
    industry = industry or "B2B technology / digital services"
    region = brief.get("region") or company.get("region") or (config.get("filters") or {}).get("region")
    country = brief.get("country") or company.get("country")
    city = brief.get("city") or company.get("city")
    location = ", ".join(dict.fromkeys(str(x) for x in (city, country, region) if x))

    flagship = brief.get("flagship_services") or []
    services = brief.get("services") or flagship
    tech = brief.get("technologies") or []
    audience = brief.get("target_audience") or []
    industries = brief.get("industries_targeted") or []
    keywords = brief.get("keywords") or []
    differentiators = brief.get("differentiators") or []
    pain_points = brief.get("pain_points") or []
    positioning = brief.get("positioning") or dna.get("positioning") or company.get("positioning")
    value_prop = (
        brief.get("value_proposition")
        or dna.get("value_proposition")
        or company.get("value_proposition")
        or positioning
    )
    if not pain_points:
        pain_points = _infer_pain_points(
            services=services,
            audience=audience,
            industries=industries,
            positioning=positioning,
            value_prop=value_prop,
        )

    site_blurb = _clip(
        website.get("tagline")
        or website.get("summary")
        or website.get("description")
        or company.get("description")
        or "",
        420,
    )

    who = _paragraph(
        f"{name} is a {industry} company"
        + (f" based in {location}" if location else "")
        + ".",
        f"Website: {brief['website']}." if brief.get("website") else "",
        f"In their own words: {site_blurb}" if site_blurb else "",
        f"Positioning: {_clip(positioning, 320)}" if positioning else "",
    )

    doing_bits = []
    if flagship:
        doing_bits.append(f"Core offerings center on {_join(flagship, limit=6)}.")
    elif services:
        doing_bits.append(f"They deliver {_join(services, limit=8)}.")
    if services and flagship and len(services) > len(flagship):
        extras = [s for s in services if s not in flagship][:10]
        if extras:
            doing_bits.append(f"Broader portfolio also includes {_join(extras, limit=10)}.")
    if tech:
        doing_bits.append(f"Delivery stack / capabilities: {_join(tech, limit=12)}.")
    if value_prop and value_prop != positioning:
        doing_bits.append(f"Value they sell: {_clip(value_prop, 280)}")
    doing = _paragraph(*doing_bits) or f"{name} provides {industry} solutions."

    audience_bits = []
    if audience:
        audience_bits.append(f"Primary buyers / users: {_join(audience, limit=10)}.")
    if industries:
        audience_bits.append(f"Vertical focus: {_join(industries, limit=8)}.")
    if keywords:
        market_kw = [k for k in keywords if k not in services][:12] or keywords[:12]
        audience_bits.append(f"Demand / search language: {_join(market_kw, limit=12)}.")
    if not audience_bits:
        audience_bits.append(
            f"Likely buyers are organizations seeking {industry} partners"
            + (f" in {location}" if location else "")
            + "."
        )
    who_buys = _paragraph(*audience_bits)

    pains = [f"Solve for: {p}" if not p.lower().startswith("solve") else p for p in pain_points[:8]]
    if not pains:
        pains = ["Customer pain points were not explicit on-site; infer from service overlap during competitor matching."]

    market = _marketplace_line(brief)
    edge_lines = []
    if differentiators:
        edge_lines.append(f"Claimed edge: {_join(differentiators, limit=8)}.")
    if brief.get("pricing_signals"):
        edge_lines.append(f"Commercial signals: {_join(brief['pricing_signals'], limit=6)}.")
    edge = _paragraph(*edge_lines)

    ig = brief.get("instagram") or {}
    li = brief.get("linkedin") or {}
    gtm_lines: list[str] = []
    if ig.get("username") or ig.get("analyzed"):
        themes = _join(ig.get("themes") or ig.get("categories") or [], limit=6)
        gtm_lines.append(
            "Instagram @"
            + str(ig.get("username") or "n/a")
            + (f" ({ig.get('followers')} followers)" if ig.get("followers") is not None else "")
            + (f"; messaging themes: {themes}" if themes else "")
            + (f"; bio: {_clip(ig.get('bio'), 160)}" if ig.get("bio") else "")
        )
    if li.get("url") or li.get("analyzed"):
        themes = _join(li.get("themes") or [], limit=6)
        gtm_lines.append(
            "LinkedIn "
            + str(li.get("url") or "analyzed")
            + (f"; themes: {themes}" if themes else "")
            + (f"; company size: {li.get('company_size')}" if li.get("company_size") else "")
            + ("; currently hiring" if li.get("is_hiring") else "")
        )

    match_lines = [
        f"Match competitors that sell overlapping services ({_join(flagship or services, limit=6) or industry}).",
        f"Same buyer segment: {_join(audience, limit=6) or 'similar B2B buyers'}.",
        f"Same marketplace / geography: {_join(brief.get('geography') or ([location] if location else []), limit=5) or 'overlapping regions'}.",
        "Prefer true category peers fighting for the same deals - not generic directories or loosely related brands.",
    ]

    blocks = [
        f"# {name} - Company Snapshot",
        _section("What the company is", who),
        _section("What they do", doing),
        _section("Target audience", who_buys),
        _section("Pain points they address", pains),
        _section("Marketplace", market) if market else "",
        _section("Positioning & edge", edge) if edge else "",
        _section("Go-to-market signals", gtm_lines) if gtm_lines else "",
        _section("How to find real competitors", match_lines),
    ]
    text = "\n\n".join(block for block in blocks if block).strip()
    return _clip(text, _MAX_SUMMARY_CHARS)


def build_company_summary_payload(state: dict[str, Any]) -> dict[str, Any]:
    config = state.get("config") or {}
    company = dict(state.get("company_profile") or config.get("company") or {})
    analysis = dict(state.get("company_analysis") or {})
    dna = dict(analysis.get("company_dna") or {})
    signals = dict(config.get("company_signals") or {})
    discovery = dict(state.get("discovery_features") or {})

    ig_wrap = analysis.get("user_instagram") or {}
    ig = ig_wrap.get("instagram") or analysis.get("instagram") or {}
    ig_profile = ig_wrap.get("profile") or {}
    li_block = analysis.get("user_linkedin") or {}
    li = (
        li_block.get("linkedin_analysis")
        or li_block.get("analysis")
        or li_block.get("linkedin")
        or {}
    )
    website = dict(analysis.get("website") or state.get("web_crawl") or {})
    website_available = _website_has_dna(website, company)

    ig_themes = _merge_unique(
        _list(ig.get("content_themes")),
        _list(ig.get("themes")),
        _list(discovery.get("instagram_content_themes")),
        _list(signals.get("instagram_content_themes")),
        limit=15,
    )
    ig_categories = _merge_unique(
        _list(ig.get("content_categories")),
        _list(discovery.get("instagram_content_categories")),
        _list(signals.get("instagram_content_categories")),
        limit=12,
    )
    ig_hashtags = _merge_unique(
        _list(ig.get("top_hashtags")),
        _list(ig.get("hashtags")),
        _list(discovery.get("instagram_hashtags")),
        limit=20,
    )
    ig_bio = (
        ig_profile.get("biography")
        or ig_profile.get("bio")
        or company.get("bio")
        or signals.get("instagram_bio")
    )
    li_themes = _merge_unique(
        _list(li.get("content_themes")),
        _list(li_block.get("linkedin_content_themes")),
        _list(signals.get("linkedin_content_themes")),
        limit=15,
    )
    li_specialties = _merge_unique(
        _list(li.get("specialties")),
        _list(li_block.get("specialties")),
        _list(signals.get("linkedin_specialties")),
        limit=20,
    )

    # DNA fields: website first; LinkedIn only if website DNA is missing. Never Instagram.
    services = _prefer_website_then_linkedin(
        website_values=_merge_unique(
            _list(website.get("services")),
            _list(website.get("products")),
            _list(company.get("services")) if website_available else [],
            _list(dna.get("services")) if website_available else [],
            limit=30,
        ),
        linkedin_values=_merge_unique(li_specialties, _list(li.get("services")), limit=20),
        website_available=website_available,
        limit=30,
    )
    flagship = _merge_unique(
        _list(company.get("flagship_services")) if website_available else [],
        services[:3],
        limit=8,
    )
    technologies = _prefer_website_then_linkedin(
        website_values=_merge_unique(
            _list(website.get("technologies")),
            _list(company.get("technologies")) if website_available else [],
            _list(dna.get("technologies")) if website_available else [],
            limit=30,
        ),
        linkedin_values=li_specialties,
        website_available=website_available,
        limit=30,
    )
    keywords = _prefer_website_then_linkedin(
        website_values=_merge_unique(
            _list(website.get("keywords")),
            _list(website.get("features")),
            _list(company.get("keywords")) if website_available else [],
            _list(dna.get("keywords")) if website_available else [],
            limit=40,
        ),
        linkedin_values=_merge_unique(li_themes, li_specialties, limit=20),
        website_available=website_available,
        limit=40,
    )
    audience = _prefer_website_then_linkedin(
        website_values=_merge_unique(
            _list(website.get("target_audience")),
            _list(company.get("target_audience")) if website_available else [],
            _list(dna.get("target_audience")) if website_available else [],
            limit=20,
        ),
        linkedin_values=_list(li.get("target_audience")),
        website_available=website_available,
        limit=20,
    )
    industries = _prefer_website_then_linkedin(
        website_values=_merge_unique(
            _list(website.get("industries")),
            _list(company.get("industries")) if website_available else [],
            limit=15,
        ),
        linkedin_values=_list(li.get("industries")),
        website_available=website_available,
        limit=15,
    )
    geography = _merge_unique(
        _list([company.get("region"), company.get("country"), company.get("city")]),
        _list((config.get("filters") or {}).get("region")),
        _list(company.get("geography")),
        limit=10,
    )
    differentiators = _prefer_website_then_linkedin(
        website_values=_merge_unique(
            _list(website.get("differentiators")),
            _list(company.get("differentiators")),
            _list(dna.get("differentiators")),
            _list(company.get("why_choose_us")),
            limit=12,
        ),
        linkedin_values=[],
        website_available=website_available,
        limit=12,
    )
    pricing = _prefer_website_then_linkedin(
        website_values=_merge_unique(
            _list(website.get("pricing_model") or website.get("pricing")),
            _list(company.get("pricing")),
            _list(company.get("engagement_models")),
            _list(dna.get("pricing")),
            limit=10,
        ),
        linkedin_values=[],
        website_available=website_available,
        limit=10,
    )

    business_model = _first_nonempty(
        website.get("business_model") if website_available else None,
        company.get("business_model") if website_available else None,
        dna.get("business_model") if website_available else None,
        li.get("business_model"),
        li_block.get("business_model"),
        company.get("business_model"),
        dna.get("business_model"),
    )
    positioning = _first_nonempty(
        website.get("positioning") if website_available else None,
        dna.get("positioning") if website_available else None,
        company.get("positioning") if website_available else None,
        li.get("positioning"),
        company.get("positioning"),
        dna.get("positioning"),
    )
    raw_vp = _first_nonempty(
        website.get("value_proposition") if website_available else None,
        dna.get("value_proposition") if website_available else None,
        company.get("value_proposition") if website_available else None,
        li.get("value_proposition"),
        company.get("value_proposition"),
        dna.get("value_proposition"),
    )
    raw_industry = _first_nonempty(
        (website.get("industries") or [None])[0] if website_available else None,
        company.get("industry") if website_available else None,
        industries[0] if industries else None,
        li.get("industry"),
        company.get("industry"),
        flagship[0] if flagship else None,
        "B2B technology / digital services",
    )

    # One unified pain list: website + inferred offer pains + IG/LI content pains.
    pain_points = _merge_unique(
        _list(website.get("pain_points")),
        _list(company.get("pain_points")),
        _list(analysis.get("pain_points")),
        _list(analysis.get("audience_pain_points")),
        _list(dna.get("pain_points")),
        _infer_pain_points(
            services=services,
            audience=audience,
            industries=industries,
            positioning=positioning,
            value_prop=raw_vp if not _same_message(raw_vp, positioning) else None,
        ),
        _pains_from_social_signals(
            ig_themes=ig_themes,
            ig_categories=ig_categories,
            ig_bio=str(ig_bio or ""),
            li_themes=li_themes,
            li_specialties=li_specialties,
        ),
        limit=12,
    )

    value_proposition = _build_value_proposition(
        name=company.get("name") or config.get("company_name"),
        services=services,
        audience=audience,
        industries=industries,
        geography=geography,
        pain_points=pain_points,
        positioning=positioning,
        existing_vp=raw_vp,
    )

    brief = {
        "name": company.get("name") or config.get("company_name"),
        "website": company.get("website") or config.get("company_website") or website.get("url"),
        "industry": raw_industry,
        "region": company.get("region") or (config.get("filters") or {}).get("region"),
        "country": company.get("country"),
        "city": company.get("city"),
        "geography": geography,
        "services": services,
        "flagship_services": flagship,
        "technologies": technologies,
        "keywords": keywords,
        "target_audience": audience,
        "industries_targeted": industries,
        "business_model": business_model,
        "pricing_signals": pricing,
        "positioning": positioning,
        "value_proposition": value_proposition,
        "differentiators": differentiators,
        "pain_points": pain_points,
        "dna_source": "website" if website_available and (technologies or services or business_model) else (
            "linkedin" if (li_specialties or li_themes) else "company"
        ),
        "instagram": {
            "username": company.get("instagram_username") or ig_wrap.get("username"),
            "followers": ig.get("followers") or ig_profile.get("followers_count"),
            "avg_engagement_rate": ig.get("avg_engagement_rate"),
            "primary_format": ig.get("primary_format"),
            "themes": ig_themes,
            "categories": ig_categories,
            "hashtags": ig_hashtags[:10],
            "bio": ig_bio,
            "analyzed": bool(config.get("user_instagram_analyzed") or ig),
        },
        "linkedin": {
            "url": company.get("linkedin_url") or li_block.get("linkedin_url"),
            "themes": li_themes,
            "is_hiring": bool(li.get("is_hiring") or analysis.get("is_hiring") or li_block.get("is_hiring")),
            "company_size": li.get("company_size") or li_block.get("company_size") or company.get("company_size"),
            "specialties": li_specialties if not website_available else [],
            "analyzed": bool(config.get("user_linkedin_analyzed") or li or li_block.get("linkedin_posts")),
        },
        "website_signals": {
            "services": _list(website.get("services"))[:20],
            "technologies": _list(website.get("technologies"))[:20],
            "industries": _list(website.get("industries"))[:15],
            "summary": _clip(website.get("summary") or website.get("description") or "", 420),
            "crawled": bool(website),
        },
    }

    summary_text = _build_impactful_summary_text(
        company=company,
        config=config,
        brief=brief,
        website=website,
        dna=dna,
    )

    # Enrich company object so competitor nodes inherit structured DNA.
    enriched_company = {
        **company,
        "name": brief.get("name") or company.get("name"),
        "website": brief.get("website") or company.get("website"),
        "industry": brief.get("industry") or company.get("industry"),
        "services": services or company.get("services") or [],
        "flagship_services": flagship or company.get("flagship_services") or [],
        "technologies": technologies or company.get("technologies") or [],
        "keywords": keywords or company.get("keywords") or [],
        "target_audience": audience or company.get("target_audience") or [],
        "pain_points": pain_points,
        "business_model": business_model or company.get("business_model"),
        "positioning": brief.get("positioning") or company.get("positioning"),
        "value_proposition": brief.get("value_proposition") or company.get("value_proposition"),
        "instagram_username": company.get("instagram_username"),
        "instagram_url": company.get("instagram_url"),
        "linkedin_url": company.get("linkedin_url") or brief.get("linkedin", {}).get("url"),
    }
    for key in ("c_level", "c_level_count", "employees", "employee_count", "niche"):
        enriched_company.pop(key, None)

    enriched_signals = {
        "company_name": enriched_company.get("name"),
        "industry": enriched_company.get("industry"),
        "website": enriched_company.get("website"),
        "services": services,
        "flagship_services": flagship,
        "technologies": technologies,
        "keywords": keywords,
        "target_industries": industries or audience,
        "instagram_username": enriched_company.get("instagram_username"),
        "linkedin_url": enriched_company.get("linkedin_url"),
        "instagram_content_themes": ig_themes,
        "linkedin_content_themes": li_themes,
        "dna_source": brief.get("dna_source"),
    }

    clean_analysis = {
        key: value
        for key, value in analysis.items()
        if key not in {"c_level", "c_level_count", "employees", "employee_count"}
    }

    return {
        "version": 2,
        "source": "analyzecompany",
        "brief": brief,
        "summary_text": summary_text,
        "company": enriched_company,
        "company_profile": enriched_company,
        "company_analysis": {
            **clean_analysis,
            "company_dna": {
                **dna,
                "services": services,
                "technologies": technologies,
                "keywords": keywords,
                "target_audience": audience,
                "pain_points": pain_points,
                "positioning": brief.get("positioning"),
                "value_proposition": brief.get("value_proposition"),
                "differentiators": differentiators,
                "pricing": pricing,
                "business_model": brief.get("business_model"),
            },
            "summary_text": summary_text,
        },
        "web_crawl": state.get("web_crawl") or website,
        "company_posts": state.get("company_posts") or analysis.get("instagram_posts") or [],
        "linkedin_posts": state.get("linkedin_posts") or li_block.get("linkedin_posts") or [],
        "discovery_features": {
            **discovery,
            "services": services,
            "keywords": keywords,
            "target_audience": audience,
            "content_themes": ig_themes or li_themes,
        },
        "company_signals": enriched_signals,
        "filters": config.get("filters") or {},
        # Lean patch for API/hydrate — no duplicated summary_text blobs.
        "config_patch": {
            "company": enriched_company,
            "company_name": enriched_company.get("name"),
            "company_description": summary_text,
            "company_website": enriched_company.get("website"),
            "company_instagram_username": enriched_company.get("instagram_username"),
            "company_linkedin_url": enriched_company.get("linkedin_url"),
            "company_signals": enriched_signals,
            "detected_niche": brief.get("industry"),
            "niche_keywords": keywords[:20],
            "user_instagram_analyzed": bool(config.get("user_instagram_analyzed")),
            "user_linkedin_analyzed": bool(config.get("user_linkedin_analyzed")),
            "skip_company_analysis": True,
        },
    }


async def GenerateCompanySummaryNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    payload = build_company_summary_payload(state)
    state["company_summary"] = payload
    state["company_summary_text"] = payload.get("summary_text") or ""

    if payload.get("company_profile"):
        state["company_profile"] = payload["company_profile"]
    if payload.get("company_analysis"):
        state["company_analysis"] = payload["company_analysis"]
    config = dict(state.get("config") or {})
    patch = payload.get("config_patch") or {}
    config.update({k: v for k, v in patch.items() if v is not None})
    if payload.get("company"):
        config["company"] = payload["company"]
    state["config"] = config

    log_event(
        "2_summary",
        "Impactful company snapshot ready",
        company=(payload.get("brief") or {}).get("name"),
        chars=len(state["company_summary_text"]),
        dna_source=(payload.get("brief") or {}).get("dna_source"),
        services=len((payload.get("brief") or {}).get("services") or []),
        pains=len((payload.get("brief") or {}).get("pain_points") or []),
        audience=len((payload.get("brief") or {}).get("target_audience") or []),
    )
    return state