import re
from typing import Any

from service.AnalyzeUserLinkedIn.posts import summarize_linkedin_posts
from service.AnalyzeUserLinkedIn.thoughtleadership import analyze_thought_leadership
from service.AnalyzeUserLinkedIn.topics import extract_linkedin_themes

B2B_POSITIONING_PATTERNS = (
    r"\b(enterprise|b2b|saas|platform|solution|services)\b",
    r"\b(clients?|customers?|partners?|stakeholders?)\b",
    r"\b(roi|revenue|pipeline|lead generation|demand gen)\b",
    r"\b(implementation|integration|consulting|agency)\b",
)


def analyze_b2b_positioning(
    posts: list[dict[str, Any]],
    *,
    employees: list[dict[str, Any]] | None = None,
    jobs: list[dict[str, Any]] | None = None,
    company_size: str | None = None,
) -> dict[str, Any]:
    employees = employees or []
    jobs = jobs or []
    texts = [post.get("text") or post.get("title") or "" for post in posts]
    combined = " ".join(texts).lower()

    signal_hits = [pattern for pattern in B2B_POSITIONING_PATTERNS if re.search(pattern, combined, re.I)]
    themes = extract_linkedin_themes(posts)
    theme_labels = [item.get("theme") for item in themes if item.get("theme")]

    positioning_focus: list[str] = []
    if any("hiring" in (theme or "").lower() for theme in theme_labels):
        positioning_focus.append("Talent & growth")
    if any("case study" in (theme or "").lower() or "client" in (theme or "").lower() for theme in theme_labels):
        positioning_focus.append("Customer proof")
    if any("product" in (theme or "").lower() or "announcement" in (theme or "").lower() for theme in theme_labels):
        positioning_focus.append("Product marketing")
    if analyze_thought_leadership(posts).get("is_thought_leader"):
        positioning_focus.append("Thought leadership")

    return {
        "b2b_signals": signal_hits[:8],
        "positioning_focus": positioning_focus or ["General B2B brand"],
        "company_size": company_size,
        "employee_count": len(employees),
        "active_hiring": bool(jobs),
        "open_roles": len(jobs),
    }


def build_linkedin_analysis(
    posts: list[dict[str, Any]],
    *,
    employees: list[dict[str, Any]] | None = None,
    jobs: list[dict[str, Any]] | None = None,
    company_size: str | None = None,
) -> dict[str, Any]:
    employees = employees or []
    jobs = jobs or []
    summary = summarize_linkedin_posts(posts)
    thought_leadership = analyze_thought_leadership(posts)
    b2b = analyze_b2b_positioning(
        posts,
        employees=employees,
        jobs=jobs,
        company_size=company_size,
    )

    return {
        **summary,
        **thought_leadership,
        **b2b,
        "employee_count": len(employees),
        "job_openings_count": len(jobs),
        "is_hiring": bool(jobs),
        "company_size": company_size,
    }
