from __future__ import annotations
import re
from typing import Any

BUSINESS_SIGNAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "hiring": (r"\b(hiring|we're hiring|we are hiring|join our team|open role|job opening)\b",),
    "funding": (r"\b(funding|raised|series [a-d]|seed round|investment|investor)\b",),
    "acquisition": (r"\b(acquired|acquisition|merger|merged with)\b",),
    "expansion": (r"\b(expansion|expanding|new office|new market|global launch)\b",),
    "awards": (r"\b(award|awarded|recognized|winner|top \d+|best .* company)\b",),
    "events": (r"\b(webinar|conference|summit|expo|workshop|event)\b",),
    "partnerships": (r"\b(partner(?:ship)?|collaborat(?:e|ion)|alliance|integrat(?:e|ion) with)\b",),
    "press_releases": (r"\b(press release|announced|announcement|launched)\b",),
    "speaking_events": (r"\b(speaking at|keynote|speaker|panel discussion)\b",),
    "podcasts": (r"\b(podcast|episode \d+|listen on spotify|apple podcasts)\b",),
}

CONTENT_TYPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "case_studies": (r"\b(case study|client success|customer story|success story)\b",),
    "ai_posts": (r"\b(artificial intelligence|\bai\b|machine learning|genai|generative ai|llm)\b",),
    "blogs": (r"\b(blog|article|read more on our blog|new post)\b",),
    "videos": (r"\b(video|youtube|watch now|webinar replay)\b",),
    "product_launches": (r"\b(product launch|new feature|introducing|now available)\b",),
}

REVIEW_PLATFORMS = {
    "clutch": (r"clutch\.co", r"clutch"),
    "g2": (r"g2\.com", r"\bg2\b"),
    "trustpilot": (r"trustpilot\.com", r"trustpilot"),
    "google_reviews": (r"google\.com/maps", r"google reviews", r"g\.page"),
}

TECHNOLOGY_PATTERNS = (
    r"\b(python|javascript|react|node\.?js|\.net|aws|azure|gcp|docker|kubernetes|"
    r"tensorflow|pytorch|openai|chatgpt|salesforce|hubspot|power bi|tableau)\b",
)

INDUSTRY_PATTERNS = (
    r"\b(fintech|healthcare|e-commerce|retail|saas|manufacturing|logistics|"
    r"education|government|real estate|automotive|telecom|energy)\b",
)


def _match_patterns(text: str, patterns: dict[str, tuple[str, ...]]) -> dict[str, bool]:
    lowered = (text or "").lower()
    return {
        key: any(re.search(pattern, lowered, re.I) for pattern in pats)
        for key, pats in patterns.items()
    }


def extract_business_signals(text: str) -> dict[str, Any]:
    flags = _match_patterns(text, BUSINESS_SIGNAL_PATTERNS)
    active = [key for key, value in flags.items() if value]
    return {"signals": flags, "active_signals": active, "signal_count": len(active)}


def extract_content_signals(text: str) -> dict[str, Any]:
    flags = _match_patterns(text, CONTENT_TYPE_PATTERNS)
    active = [key for key, value in flags.items() if value]
    return {"content_types": flags, "active_content_types": active}


def extract_technologies_mentioned(text: str) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    for pattern in TECHNOLOGY_PATTERNS:
        for match in re.finditer(pattern, lowered, re.I):
            label = match.group(0).strip()
            if label not in found:
                found.append(label)
    return found[:15]


def extract_industries_targeted(text: str) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    for pattern in INDUSTRY_PATTERNS:
        for match in re.finditer(pattern, lowered, re.I):
            label = match.group(0).strip()
            if label not in found:
                found.append(label)
    return found[:10]


def extract_review_presence(*texts: str, links: list[str] | None = None) -> dict[str, Any]:
    combined = " ".join(texts).lower()
    link_blob = " ".join(links or []).lower()
    blob = f"{combined} {link_blob}"
    platforms: dict[str, bool] = {}
    for platform, patterns in REVIEW_PLATFORMS.items():
        platforms[platform] = any(re.search(p, blob, re.I) for p in patterns)
    return {
        "platforms": platforms,
        "present_on": [name for name, present in platforms.items() if present],
        "has_reviews": any(platforms.values()),
    }


def collect_text_blobs(entity: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("bio", "description", "tagline", "about_us", "name"):
        if entity.get(key):
            parts.append(str(entity[key]))
    intel = entity.get("website_intelligence") or {}
    for key in ("description", "positioning", "raw_markdown"):
        if intel.get(key):
            parts.append(str(intel[key]))
    for post in entity.get("linkedin_posts") or []:
        parts.append(post.get("text") or post.get("title") or "")
    for post in entity.get("instagram_posts") or []:
        parts.append(post.get("caption") or post.get("text") or "")
    li = entity.get("linkedin_analysis") or {}
    for sample in li.get("sample_posts") or []:
        parts.append(sample.get("text") or "")
    ig = entity.get("instagram_analysis") or {}
    if ig.get("bio"):
        parts.append(str(ig["bio"]))
    return " ".join(parts)


def build_extended_linkedin_profile(
    entity: dict[str, Any],
    *,
    is_user: bool = False,
) -> dict[str, Any]:
    li = entity.get("linkedin_analysis") or {}
    user_li = entity.get("user_linkedin") or {}
    if is_user and user_li:
        li = user_li.get("linkedin_analysis") or li
        employees = user_li.get("employees") or entity.get("employees") or []
        jobs = user_li.get("job_openings") or entity.get("job_openings") or []
        company_size = user_li.get("company_size") or entity.get("company_size")
    else:
        employees = entity.get("employees") or []
        jobs = li.get("job_openings") or []
        company_size = li.get("company_size")

    posts = entity.get("linkedin_posts") or user_li.get("linkedin_posts") or []
    text = collect_text_blobs(entity)
    business = extract_business_signals(text)
    content = extract_content_signals(text)

    return {
        "followers": entity.get("followers") or li.get("followers"),
        "employees": employees[:50],
        "employee_count": len(employees) or li.get("employee_count"),
        "company_size": company_size,
        "industry": entity.get("industry") or li.get("industry"),
        "specialties": entity.get("specialties") or li.get("specialties") or entity.get("services"),
        "headquarters": entity.get("headquarters") or entity.get("city") or entity.get("country"),
        "website": entity.get("website"),
        "tagline": entity.get("bio") or entity.get("tagline") or li.get("bio"),
        "hiring": business["signals"].get("hiring") or bool(jobs) or li.get("is_hiring"),
        "partnerships": business["signals"].get("partnerships"),
        "product_launches": content["content_types"].get("product_launches"),
        "funding": business["signals"].get("funding"),
        "awards": business["signals"].get("awards"),
        "case_studies": content["content_types"].get("case_studies"),
        "ai_posts": content["content_types"].get("ai_posts"),
        "blogs": content["content_types"].get("blogs"),
        "videos": content["content_types"].get("videos"),
        "hiring_trends": {
            "is_hiring": bool(jobs),
            "open_roles": len(jobs),
            "job_titles": [j.get("job_title") for j in jobs[:5] if j.get("job_title")],
        },
        "growth_trends": {
            "expansion_signal": business["signals"].get("expansion"),
            "hiring_signal": business["signals"].get("hiring"),
            "funding_signal": business["signals"].get("funding"),
        },
        "industries_targeted": extract_industries_targeted(text),
        "technologies_mentioned": extract_technologies_mentioned(text),
        "thought_leadership_score": li.get("thought_leadership_score"),
        "post_count": li.get("post_count") or len(posts),
        "content_themes": li.get("content_themes") or [],
        "business_signals": business["active_signals"],
    }
