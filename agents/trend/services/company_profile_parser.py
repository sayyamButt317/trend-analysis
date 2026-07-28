import re
from dataclasses import dataclass, field
from typing import Any


SERVICE_PATTERNS = (
    r"AI Development",
    r"AI Automation",
    r"Web Application Development",
    r"Mobile Application Development",
    r"DevOps",
    r"AI-Readiness",
    r"Cloud Migrations?",
    r"Staff Augmentation",
    r"AI Governance",
    r"no-code/low-code development",
    r"software development",
    r"IT services",
    r"custom software",
    r"MVP development",
)

TECH_PATTERNS = (
    r"JavaScript",
    r"\.NET",
    r"Python",
    r"AI/ML",
    r"GenAI",
    r"MERN",
    r"React",
    r"Node\.js",
    r"Flutter",
    r"DevOps",
)

INDUSTRY_PATTERNS = (
    r"fintech",
    r"fitness/wellness",
    r"e-commerce",
    r"public-sector",
    r"enterprise",
    r"SMB",
    r"government",
)

SECTION_HEADERS = {
    "services": re.compile(r"services?\s*&\s*expertise|full service list|flagship services?", re.I),
    "differentiators": re.compile(r"differentiators?\s*&\s*positioning|why a client should choose", re.I),
    "ideal_clients": re.compile(r"ideal client", re.I),
}


@dataclass
class CompanySignals:
    name: str | None = None
    services: list[str] = field(default_factory=list)
    flagship_services: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    target_industries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "services": self.services,
            "flagship_services": self.flagship_services,
            "technologies": self.technologies,
            "target_industries": self.target_industries,
            "keywords": self.keywords,
            "summary": self.summary,
        }


def normalize_profile_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = (
        text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\\t", "\t")
    )
    return normalized.strip()


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _extract_name_from_profile(profile: str, fallback: str | None = None) -> str | None:
    if fallback:
        return fallback.strip()

    profile_text = normalize_profile_text(profile)
    if not profile_text:
        return None

    lines = [line.strip() for line in profile_text.splitlines() if line.strip()]
    for line in lines[:4]:
        cleaned = re.sub(r"^(company\s*&\s*team\s*)", "", line, flags=re.I).strip()
        if not cleaned:
            continue
        if re.fullmatch(r"[A-Z &/]+", cleaned) and "LLC" not in cleaned and "Inc" not in cleaned:
            continue
        if len(cleaned) <= 80:
            return cleaned

    prefix_match = re.match(
        r"^([A-Za-z0-9][A-Za-z0-9 &.,'-]{1,70}?(?:\s+(?:LLC|Inc|Ltd|Corporation|Pvt\.?|L\.L\.C\.))?)",
        profile_text,
        re.I,
    )
    if prefix_match:
        return prefix_match.group(1).strip()

    return fallback


def _extract_numbered_items(text: str, limit: int = 5) -> list[str]:
    items: list[str] = []
    for match in re.finditer(r"(?:^\s*\d+\.\s+(.+)$)|(?:^\s*[-•]\s+(.+)$)", text, re.M):
        value = (match.group(1) or match.group(2) or "").strip()
        value = re.sub(r"\s*—.*$", "", value).strip()
        if value and len(value) <= 120:
            items.append(value)
        if len(items) >= limit:
            break
    return items


def _extract_pattern_hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            hits.append(match.group(0).strip())
    return hits


def _first_sentences(text: str, count: int = 2) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return " ".join(parts[:count]).strip()


def _section_slice(profile: str, header_pattern: re.Pattern) -> str:
    match = header_pattern.search(profile)
    if not match:
        return ""
    start = match.end()
    next_header = re.search(
        r"\n[A-Z][A-Z &/]+\n|\n[A-Z][A-Z &/]+\r",
        profile[start:],
    )
    end = start + next_header.start() if next_header else len(profile)
    return profile[start:end]


def parse_company_profile(
    profile: str | None,
    *,
    company: dict[str, Any] | None = None,
) -> CompanySignals:
    company = company or {}
    profile_text = normalize_profile_text(
        profile or company.get("profile") or company.get("description") or ""
    )

    signals = CompanySignals(
        name=_extract_name_from_profile(profile_text, company.get("name")),
        services=[str(item).strip() for item in (company.get("services") or []) if str(item).strip()],
        flagship_services=[
            str(item).strip() for item in (company.get("flagship_services") or []) if str(item).strip()
        ],
        technologies=[str(item).strip() for item in (company.get("technologies") or []) if str(item).strip()],
        target_industries=[
            str(item).strip() for item in (company.get("target_industries") or []) if str(item).strip()
        ],
        keywords=[str(item).strip() for item in (company.get("keywords") or []) if str(item).strip()],
    )

    if not profile_text:
        signals.summary = company.get("description")
        return signals

    services_section = _section_slice(profile_text, SECTION_HEADERS["services"]) or profile_text
    ideal_clients_section = _section_slice(profile_text, SECTION_HEADERS["ideal_clients"])

    if not signals.services:
        signals.services = _extract_pattern_hits(services_section, SERVICE_PATTERNS)
        signals.services.extend(_extract_numbered_items(services_section, limit=8))

    if not signals.flagship_services:
        flagship_match = re.search(
            r"flagship services.*?:(.*?)(?:\n\n|\nCore technologies|\nTechtimize holds|\Z)",
            profile_text,
            re.I | re.S,
        )
        if flagship_match:
            signals.flagship_services = _extract_numbered_items(flagship_match.group(1), limit=5)
        if not signals.flagship_services:
            signals.flagship_services = signals.services[:3]

    if not signals.technologies:
        signals.technologies = _extract_pattern_hits(profile_text, TECH_PATTERNS)

    if not signals.target_industries:
        signals.target_industries = _extract_pattern_hits(
            ideal_clients_section or profile_text,
            INDUSTRY_PATTERNS,
        )

    auto_keywords: list[str] = []
    for bucket in (
        signals.flagship_services,
        signals.services[:5],
        signals.technologies[:4],
    ):
        for item in bucket:
            short = re.sub(r"\s+", " ", item).strip()
            if short and len(short) <= 60:
                auto_keywords.append(short)

    auto_keywords.extend(
        [
            "software development company",
            "AI development agency",
            "IT services company",
            "custom software agency",
            "staff augmentation company",
        ]
    )
    signals.keywords = _unique(signals.keywords + auto_keywords)
    signals.services = _unique(signals.services)
    signals.flagship_services = _unique(signals.flagship_services)
    signals.technologies = _unique(signals.technologies)
    signals.target_industries = _unique(signals.target_industries)
    signals.summary = _first_sentences(profile_text, count=2)
    return signals




def merge_company_with_profile(company: dict[str, Any]) -> dict[str, Any]:
    profile_text = normalize_profile_text(company.get("profile") or company.get("description") or "")
    signals = parse_company_profile(profile_text, company=company)
    merged = {**company}
    merged["profile"] = profile_text or merged.get("profile")
    merged["name"] = merged.get("name") or signals.name
    merged["description"] = merged.get("description") or signals.summary
    if not merged.get("website"):
        website_match = re.search(r"https?://(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", signals.summary or "", re.I)
        if website_match:
            merged["website"] = website_match.group(0)
    merged["services"] = _unique([*(merged.get("services") or []), *signals.services])
    merged["flagship_services"] = _unique(
        [*(merged.get("flagship_services") or []), *signals.flagship_services]
    )
    merged["technologies"] = _unique([*(merged.get("technologies") or []), *signals.technologies])
    merged["target_industries"] = _unique(
        [*(merged.get("target_industries") or []), *signals.target_industries]
    )
    merged["extracted_keywords"] = signals.keywords
    merged["company_signals"] = signals.to_dict()
    return merged
