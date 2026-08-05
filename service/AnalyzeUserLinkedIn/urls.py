import re

LINKEDIN_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w.]+)\.?linkedin\.com/(company|in)/([A-Za-z0-9_-]+)/?",
    re.I,
)

COMPANY_SUFFIX_RE = re.compile(
    r"\b(LLC|L\.L\.C\.|Inc\.?|Ltd\.?|Limited|Corporation|Corp\.?|Pvt\.?|Co\.?)\b",
    re.I,
)


def company_name_to_slug(company_name: str) -> str:
    """Convert a user-provided company name to a LinkedIn company slug."""
    name = (company_name or "").strip()
    name = COMPANY_SUFFIX_RE.sub("", name).strip(" ,.-")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


def build_company_urls_from_name(
    company_name: str,
    *,
    linkedin_url: str | None = None,
) -> dict[str, str]:
    """Build LinkedIn company URLs from name and optional known company URL."""
    normalized = normalize_linkedin_url(linkedin_url or "")
    if normalized and "/company/" in normalized:
        slug = normalized.split("/company/")[1].split("/")[0]
    else:
        slug = company_name_to_slug(company_name)
    base = f"https://www.linkedin.com/company/{slug}"
    return {
        "slug": slug,
        "company_url": f"{base}/",
        "posts_url": f"{base}/posts/?feedView=all",
        "people_url": f"{base}/people/",
        "jobs_url": f"{base}/jobs/",
    }


def normalize_linkedin_url(url_or_slug: str) -> str | None:
    value = (url_or_slug or "").strip().rstrip("/")
    if not value:
        return None
    if "linkedin.com" in value:
        match = LINKEDIN_URL_RE.search(value if value.startswith("http") else f"https://{value.lstrip('www.')}")
        if match:
            kind, slug = match.group(1).lower(), match.group(2)
            return f"https://www.linkedin.com/{kind}/{slug}/"
        if "/company/" in value or "/in/" in value:
            return value if value.startswith("http") else f"https://www.{value.lstrip('www.')}"
        return None
    return f"https://www.linkedin.com/company/{value}/"


def linkedin_posts_path(
    linkedin_url: str | None = None,
    *,
    company_name: str | None = None,
) -> str:
    if company_name:
        return build_company_urls_from_name(company_name)["posts_url"]

    normalized = (linkedin_url or "").rstrip("/")
    if not normalized:
        return ""
    if "/in/" in normalized:
        return f"{normalized}/recent-activity/all/"
    base = company_base_url(normalized)
    return f"{base}/posts/?feedView=all"


def company_base_url(linkedin_url: str | None = None, *, company_name: str | None = None) -> str:
    if company_name:
        return build_company_urls_from_name(company_name)["company_url"].rstrip("/")
    normalized = normalize_linkedin_url(linkedin_url or "")
    if not normalized:
        return (linkedin_url or "").rstrip("/")
    if "/company/" in normalized:
        slug = normalized.split("/company/")[1].split("/")[0]
        return f"https://www.linkedin.com/company/{slug}"
    if "/in/" in normalized:
        slug = normalized.split("/in/")[1].split("/")[0]
        return f"https://www.linkedin.com/in/{slug}"
    return normalized.rstrip("/")


def company_slug(linkedin_url: str | None = None, *, company_name: str | None = None) -> str:
    if company_name:
        return company_name_to_slug(company_name)
    base = company_base_url(linkedin_url)
    if "/company/" in base:
        return base.split("/company/")[1].split("/")[0]
    return ""
