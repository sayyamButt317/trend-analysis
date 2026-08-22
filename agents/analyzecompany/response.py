"""Build a slim analyze-company API response (drop nested duplicates)."""

from __future__ import annotations

from typing import Any


_COMPANY_KEEP = (
    "name",
    "website",
    "industry",
    "region",
    "country",
    "city",
    "instagram_username",
    "instagram_url",
    "linkedin_url",
    "services",
    "flagship_services",
    "technologies",
    "keywords",
    "target_audience",
    "pain_points",
    "positioning",
    "value_proposition",
    "business_model",
)


_BRIEF_KEEP = (
    "name",
    "website",
    "industry",
    "region",
    "country",
    "city",
    "geography",
    "services",
    "flagship_services",
    "technologies",
    "keywords",
    "target_audience",
    "industries_targeted",
    "business_model",
    "pricing_signals",
    "positioning",
    "value_proposition",
    "differentiators",
    "pain_points",
)


def _pick(source: dict[str, Any] | None, keys: tuple[str, ...] | list[str]) -> dict[str, Any]:
    data = source or {}
    out: dict[str, Any] = {}
    for key in keys:
        value = data.get(key)
        if value is None or value == "" or value == [] or value == {}:
            continue
        out[key] = value
    return out


def _is_junk_label(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lower = text.lower()
    return (
        "mostly carousel" in lower
        or "focused on" in lower
        or lower.startswith("share_pct")
        or "%" in text and "carousel" in lower
    )


def _clean_list(values: Any, *, limit: int = 25) -> list[Any]:
    if not isinstance(values, list):
        return []
    cleaned: list[Any] = []
    seen: set[str] = set()
    for item in values:
        if isinstance(item, str):
            if _is_junk_label(item):
                continue
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            cleaned.append(item.strip())
        elif item is not None:
            cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _slim_instagram(analysis: dict[str, Any] | None) -> dict[str, Any]:
    ig = analysis or {}
    block = (
        ig.get("instagram")
        or (ig.get("user_instagram") or {}).get("instagram")
        or (ig.get("user_instagram") or {}).get("instagram_analysis")
        or {}
    )
    slim = _pick(
        block,
        [
            "avg_engagement_rate",
            "primary_format",
            "primary_content_category",
            "posting_frequency",
            "content_themes",
            "content_categories",
            "top_hashtags",
            "followers",
        ],
    )
    # Drop noisy sentence-style niche/focus fields.
    return slim


def slim_company_analysis(analysis: dict[str, Any] | None) -> dict[str, Any]:
    raw = analysis or {}
    dna = dict(raw.get("company_dna") or {})
    for key in ("services", "keywords", "technologies", "target_audience", "industries", "pricing", "differentiators", "pain_points"):
        if key in dna:
            dna[key] = _clean_list(dna.get(key))
    return {
        "company_dna": dna,
        "is_hiring": raw.get("is_hiring"),
        "company_size": raw.get("company_size"),
        "job_openings": (raw.get("job_openings") or [])[:5],
        "linkedin_url": raw.get("linkedin_url"),
        "linkedin_content_themes": raw.get("linkedin_content_themes") or [],
        "instagram": _slim_instagram(raw),
        "social_handles": raw.get("social_handles") or {},
    }


def slim_brief(brief: dict[str, Any] | None) -> dict[str, Any]:
    raw = brief or {}
    out = _pick(raw, _BRIEF_KEEP)
    for key in ("services", "flagship_services", "technologies", "keywords", "target_audience", "differentiators", "pain_points", "pricing_signals", "industries_targeted", "geography"):
        if key in out:
            out[key] = _clean_list(out.get(key))
    ig = raw.get("instagram") or {}
    if ig.get("username") or ig.get("followers") is not None:
        out["instagram"] = _pick(ig, ["username", "followers", "avg_engagement_rate", "primary_format", "analyzed"])
    li = raw.get("linkedin") or {}
    if li.get("url") or li.get("analyzed"):
        out["linkedin"] = _pick(li, ["url", "is_hiring", "company_size", "analyzed"])
    website = raw.get("website_signals") or {}
    if website.get("summary") or website.get("crawled"):
        out["website_signals"] = {
            "summary": website.get("summary"),
            "crawled": bool(website.get("crawled")),
        }
    return out


def slim_config_patch(
    patch: dict[str, Any] | None,
    *,
    company: dict[str, Any] | None = None,
    summary_text: str = "",
) -> dict[str, Any]:
    """Competitor hydrate needs flags + lean company — not nested analysis dumps."""
    raw = dict(patch or {})
    lean_company = slim_company_object(company or raw.get("company") or {})
    out: dict[str, Any] = {
        "company": lean_company,
        "company_name": raw.get("company_name") or lean_company.get("name"),
        "company_website": raw.get("company_website") or lean_company.get("website"),
        "company_instagram_username": (
            raw.get("company_instagram_username") or lean_company.get("instagram_username")
        ),
        "company_linkedin_url": raw.get("company_linkedin_url") or lean_company.get("linkedin_url"),
        "detected_niche": raw.get("detected_niche") if not _is_junk_label(raw.get("detected_niche")) else None,
        "niche_keywords": _clean_list(raw.get("niche_keywords"), limit=20),
        "user_instagram_analyzed": bool(raw.get("user_instagram_analyzed")),
        "user_linkedin_analyzed": bool(raw.get("user_linkedin_analyzed")),
        "skip_company_analysis": True,
    }
    # One pointer to DNA text — competitor handoff uses top-level summary_text.
    if summary_text:
        out["company_description"] = summary_text
    # Drop empties / None
    return {k: v for k, v in out.items() if v is not None and v != "" and v != []}


def slim_company_object(company: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(company or {})
    slim = _pick(data, _COMPANY_KEEP)
    for key in ("services", "flagship_services", "technologies", "keywords", "target_audience"):
        if key in slim:
            slim[key] = _clean_list(slim.get(key))
    if slim.get("niche") and _is_junk_label(slim["niche"]):
        slim.pop("niche", None)
    return slim


def build_slim_analyze_company_response(
    *,
    success: bool,
    error: Any = None,
    company: dict[str, Any] | None = None,
    company_profile: dict[str, Any] | None = None,
    company_analysis: dict[str, Any] | None = None,
    company_summary: dict[str, Any] | None = None,
    intelligence: dict[str, Any] | None = None,
    warnings: list[Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Public API payload — DNA once + actionable intelligence."""
    analysis = slim_company_analysis(company_analysis)
    profile = company_profile or company or {}
    summary = company_summary or {}
    summary_text = summary.get("summary_text") or ""
    lean_company = slim_company_object(profile)
    intel = intelligence or {}

    payload = {
        "success": success,
        "error": error,
        "company": lean_company,
        "company_summary": {
            "version": summary.get("version") or 2,
            "source": summary.get("source") or "analyzecompany",
            "brief": slim_brief(summary.get("brief")),
            "summary_text": summary_text,
            "config_patch": slim_config_patch(
                summary.get("config_patch"),
                company=lean_company,
                summary_text=summary_text,
            ),
        },
        "company_analysis": analysis,
        "executive_snapshot": intel.get("executive_snapshot") or {},
        "digital_presence": intel.get("digital_presence") or {},
        "market_position": intel.get("market_position") or {},
        "positioning_analysis": intel.get("positioning_analysis") or {},
        "strengths_and_weaknesses": intel.get("strengths_and_weaknesses") or {},
        "growth_opportunities": intel.get("growth_opportunities") or [],
        "recommended_actions": intel.get("recommended_actions") or [],
        "warnings": warnings or [],
        "meta": meta or {},
    }
    return payload
