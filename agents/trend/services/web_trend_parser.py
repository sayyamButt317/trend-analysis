import re
from collections import Counter
from typing import Any

from agents.trend.Nodes.common import GENERIC_HASHTAGS
from agents.trend.services.web_trend_sources import SOURCE_WEIGHTS

TREND_HEADER_RE = re.compile(
    r"^#{2,3}\s*\*{0,2}(.+?)\*{0,2}\s*$",
    re.MULTILINE,
)
HASHTAG_RE = re.compile(r"#([A-Za-z][A-Za-z0-9_]{2,49})")
QUOTED_TREND_RE = re.compile(r"[\"“]([^\"”]{3,80})[\"”]\s+trend", re.IGNORECASE)
TIMESTAMP_RE = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\w{3}\s+\d{1,2}\s+\d{4}|GMT|Coordinated Universal Time",
    re.IGNORECASE,
)

TOPIC_FOCUS_ALIASES = frozenset(
    {
        "breaking_topics",
        "creator_updates",
        "cross_platform_trends",
        "social_media_trends",
        "creator_trends",
        "creator_discussions",
        "content_strategy",
        "engagement",
        "analytics",
        "benchmarks",
        "marketing",
    }
)

JUNK_HASHTAGS = GENERIC_HASHTAGS | frozenset(
    {
        "fff",
        "ffffff",
        "primaryimage",
        "organization",
        "ez",
        "css",
        "html",
        "http",
        "https",
        "www",
        "utm",
        "src",
        "alt",
        "div",
        "span",
        "class",
        "style",
        "media",
        "font",
        "color",
        "background",
        "padding",
        "margin",
        "width",
        "height",
        "instagram",
        "facebook",
        "twitter",
    }
)


def _is_valid_hashtag(tag: str) -> bool:
    if not tag or tag in JUNK_HASHTAGS:
        return False
    if re.fullmatch(r"[0-9a-f]{3,8}", tag):
        return False
    if len(tag) < 3:
        return False
    return True

SKIP_HEADERS = frozenset(
    {
        "most popular instagram hashtags",
        "best hashtags for engagement",
        "niche-specific hashtags",
        "why instagram hashtags matter",
        "references",
        "see also",
        "origin and spread",
        "reception",
        "product",
        "pricing",
        "resources",
        "log in or sign up for x",
        "relevant people",
        "trending now",
        "post",
    }
)


def _clean_header(text: str) -> str:
    cleaned = re.sub(r"\*{1,2}", "", text or "").strip()
    cleaned = re.sub(r"^\(\w+ \d+, \d{4}\)\s*", "", cleaned)
    return cleaned.strip(" .")


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def parse_reel_formats(text: str, *, source: str) -> list[dict[str, Any]]:
    formats: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in TREND_HEADER_RE.finditer(text):
        header = _clean_header(match.group(1))
        if not header or len(header) < 4 or len(header) > 120:
            continue
        lowered = header.lower()
        if lowered in SKIP_HEADERS:
            continue
        if lowered.startswith(("written by", "subscribe", "table of", "jump to")):
            continue
        if "hashtag" in lowered and "instagram" in lowered:
            continue
        key = lowered
        if key in seen:
            continue
        seen.add(key)
        formats.append(
            {
                "name": header,
                "category": header,
                "source": source,
                "type": "reel_format",
            }
        )
    for match in QUOTED_TREND_RE.finditer(text):
        name = match.group(1).strip()
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        formats.append(
            {
                "name": name,
                "category": name,
                "source": source,
                "type": "reel_format",
            }
        )
    return formats[:25]


def parse_hashtags(text: str, *, source: str) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for match in HASHTAG_RE.finditer(text):
        tag = _normalize_tag(match.group(1))
        if not _is_valid_hashtag(tag):
            continue
        counter[tag] += 1
    return [
        {"hashtag": tag, "tag": tag, "post_count": count, "source": source, "type": "hashtag"}
        for tag, count in counter.most_common(40)
    ]


def parse_culture_topics(text: str, *, source: str) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    patterns = [
        r"2026 is the new 2016",
        r"#BringBack2016",
        r"Mannequin Challenge",
        r"Pok[eé]mon Go",
        r"yellow font",
        r"Netflix documentary",
        r"nostalgia",
    ]
    lowered = text.lower()
    for pattern in patterns:
        if re.search(pattern, lowered, re.IGNORECASE):
            label = pattern.replace("\\", "").replace("[eé]", "e")
            topics.append(
                {
                    "topic": label,
                    "key": label,
                    "source": source,
                    "type": "culture_topic",
                }
            )
    return topics


def parse_general_topics(text: str, *, source: str, limit: int = 20) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    seen: set[str] = set()

    for fmt in parse_reel_formats(text, source=source):
        name = fmt.get("name") or ""
        key = name.lower()
        if name and key not in seen and len(name) >= 4:
            seen.add(key)
            topics.append(
                {
                    "topic": name,
                    "key": name,
                    "source": source,
                    "type": "topic",
                }
            )

    for match in QUOTED_TREND_RE.finditer(text):
        name = match.group(1).strip()
        key = name.lower()
        if key not in seen:
            seen.add(key)
            topics.append(
                {
                    "topic": name,
                    "key": name,
                    "source": source,
                    "type": "topic",
                }
            )

    for line in re.split(r"[\n.!?]+", text or ""):
        cleaned = _clean_header(line.strip())
        if not cleaned or len(cleaned) < 12 or len(cleaned) > 140:
            continue
        if TIMESTAMP_RE.search(cleaned):
            continue
        lowered = cleaned.lower()
        if lowered in seen or lowered in SKIP_HEADERS:
            continue
        if any(token in lowered for token in ("cookie", "privacy", "sign in", "javascript")):
            continue
        if re.search(r"\b(trend|viral|marketing|instagram|creator|algorithm|reels?)\b", lowered, re.I):
            seen.add(lowered)
            topics.append(
                {
                    "topic": cleaned,
                    "key": cleaned,
                    "source": source,
                    "type": "topic",
                }
            )
        if len(topics) >= limit:
            break

    return topics[:limit]


def parse_google_trends_page(trends: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert Google Trends RSS items into parser page format."""
    topics = [
        {
            "topic": item.get("topic") or item.get("key"),
            "key": item.get("topic") or item.get("key"),
            "source": item.get("source") or "Google Trends",
            "geo": item.get("geo"),
            "approx_traffic": item.get("approx_traffic"),
            "traffic_score": item.get("traffic_score"),
            "news_items": item.get("news_items") or [],
            "type": "google_trend",
        }
        for item in trends
    ]
    return {
        "source": "Google Trends",
        "url": "https://trends.google.com/trending",
        "reel_formats": [],
        "hashtags": [],
        "topics": topics,
        "google_trends": trends,
    }


def parse_reddit_posts(
    posts: list[dict[str, Any]],
    *,
    source: str,
    focus: str,
) -> dict[str, Any]:
    topics: list[dict[str, Any]] = []
    reel_formats: list[dict[str, Any]] = []
    seen_topics: set[str] = set()
    text_chunks: list[str] = []

    for entry in posts:
        data = entry.get("data") if isinstance(entry.get("data"), dict) else entry
        if not isinstance(data, dict):
            continue
        title = (data.get("title") or "").strip()
        selftext = (data.get("selftext") or data.get("body") or "").strip()
        flair = (data.get("link_flair_text") or data.get("flair") or "").strip()
        ups = int(data.get("ups") or data.get("score") or 0)
        if not title:
            continue

        text_chunks.extend([title, selftext, flair])
        topic_key = title.lower()
        if topic_key not in seen_topics and len(title) >= 8:
            seen_topics.add(topic_key)
            topics.append(
                {
                    "topic": title,
                    "key": title,
                    "source": source,
                    "type": "reddit_post",
                    "upvotes": ups,
                    "flair": flair or None,
                }
            )
        if flair and flair.lower() not in seen_topics:
            seen_topics.add(flair.lower())
            reel_formats.append(
                {
                    "name": flair,
                    "category": flair,
                    "source": source,
                    "type": "reddit_flair",
                }
            )

    combined = "\n".join(text_chunks)
    hashtags = parse_hashtags(combined, source=source)
    focus_set = {item.strip() for item in focus.split(",") if item.strip()}
    if focus_set & TOPIC_FOCUS_ALIASES:
        focus_set.add("topics")
    if "culture" in focus_set:
        topics.extend(parse_culture_topics(combined, source=source))
    if "topics" in focus_set:
        topics.extend(parse_general_topics(combined, source=source))

    return {
        "source": source,
        "reel_formats": reel_formats[:15],
        "hashtags": hashtags[:20],
        "topics": topics[:25],
    }


def parse_reddit_comments(
    comments: list[dict[str, Any]],
    *,
    source: str,
    focus: str,
) -> dict[str, Any]:
    topics: list[dict[str, Any]] = []
    seen_topics: set[str] = set()
    text_chunks: list[str] = []

    for entry in comments:
        data = entry.get("data") if isinstance(entry.get("data"), dict) else entry
        if not isinstance(data, dict):
            continue
        body = (data.get("body") or data.get("selftext") or "").strip()
        if not body or body in {"[deleted]", "[removed]"}:
            continue
        ups = int(data.get("ups") or data.get("score") or 0)
        subreddit = (data.get("subreddit") or "").strip()
        text_chunks.append(body)

        snippet = body.replace("\n", " ").strip()
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        topic_key = snippet.lower()
        if topic_key not in seen_topics and len(snippet) >= 15:
            seen_topics.add(topic_key)
            topics.append(
                {
                    "topic": snippet,
                    "key": snippet,
                    "source": source,
                    "type": "reddit_comment",
                    "upvotes": ups,
                    "subreddit": subreddit or None,
                }
            )

    combined = "\n".join(text_chunks)
    hashtags = parse_hashtags(combined, source=source)
    focus_set = {item.strip() for item in focus.split(",") if item.strip()}
    if focus_set & TOPIC_FOCUS_ALIASES:
        focus_set.add("topics")
    if "culture" in focus_set:
        topics.extend(parse_culture_topics(combined, source=source))
    if "topics" in focus_set:
        topics.extend(parse_general_topics(combined, source=source))

    return {
        "source": source,
        "reel_formats": [],
        "hashtags": hashtags[:20],
        "topics": topics[:25],
    }


def extract_platform_trends(parsed_pages: list[dict[str, Any]], platform: str) -> dict[str, Any]:
    platform_key = platform.lower()
    pages = [page for page in parsed_pages if (page.get("platform") or "").lower() == platform_key]
    topics: list[dict[str, Any]] = []
    hashtags: list[dict[str, Any]] = []
    reel_formats: list[dict[str, Any]] = []
    sources: list[str] = []
    post_count = 0
    seen_topics: set[str] = set()
    seen_tags: set[str] = set()
    seen_formats: set[str] = set()

    for page in pages:
        source = page.get("source")
        if source and source not in sources:
            sources.append(source)
        post_count += int(page.get("post_count") or 0)
        for topic in page.get("topics") or []:
            key = (topic.get("topic") or topic.get("key") or "").lower()
            if key and key not in seen_topics:
                seen_topics.add(key)
                topics.append(topic)
        for tag in page.get("hashtags") or []:
            label = tag.get("hashtag") or tag.get("tag")
            if label and label not in seen_tags:
                seen_tags.add(label)
                hashtags.append(tag)
        for fmt in page.get("reel_formats") or []:
            key = (fmt.get("name") or "").lower()
            if key and key not in seen_formats:
                seen_formats.add(key)
                reel_formats.append(fmt)

    return {
        "platform": platform_key,
        "source_count": len(sources),
        "post_count": post_count,
        "sources": sources,
        "topics": topics[:30],
        "hashtags": hashtags[:30],
        "reel_formats": reel_formats[:20],
        "total_items": len(topics) + len(hashtags) + len(reel_formats),
    }


def build_source_breakdown(parsed_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    breakdown: list[dict[str, Any]] = []
    for page in parsed_pages:
        source = page.get("source") or "unknown"
        reel_formats = page.get("reel_formats") or []
        hashtags = page.get("hashtags") or []
        topics = page.get("topics") or []
        google_trends = page.get("google_trends") or []
        item_count = len(reel_formats) + len(hashtags) + len(topics) + len(google_trends)
        if item_count == 0:
            continue

        base_name = source.split(" (")[0] if " (" in source else source
        breakdown.append(
            {
                "source": source,
                "platform": page.get("platform") or _platform_from_source(source),
                "url": page.get("url"),
                "weight": SOURCE_WEIGHTS.get(base_name, SOURCE_WEIGHTS.get(source, 0.5)),
                "counts": {
                    "reel_formats": len(reel_formats),
                    "hashtags": len(hashtags),
                    "topics": len(topics),
                    "google_trends": len(google_trends),
                    "total": item_count,
                },
                "reel_formats": [{"name": f.get("name")} for f in reel_formats[:5]],
                "hashtags": [
                    {"tag": h.get("hashtag") or h.get("tag"), "post_count": h.get("post_count")}
                    for h in hashtags[:8]
                ],
                "topics": [
                    {"topic": t.get("topic") or t.get("key"), "upvotes": t.get("upvotes")}
                    for t in topics[:8]
                ],
                "google_trends": [
                    {"topic": g.get("topic") or g.get("key"), "geo": g.get("geo")}
                    for g in google_trends[:5]
                ],
            }
        )

    breakdown.sort(
        key=lambda item: (
            float(item.get("weight") or 0),
            int((item.get("counts") or {}).get("total") or 0),
        ),
        reverse=True,
    )
    return breakdown


def _platform_from_source(source: str) -> str:
    lowered = (source or "").lower()
    if "reddit" in lowered:
        return "reddit"
    if lowered.startswith("x ") or lowered.startswith("x(") or " x " in lowered or lowered == "x":
        return "x"
    if "facebook" in lowered:
        return "facebook"
    if "linkedin" in lowered:
        return "linkedin"
    if "google trends" in lowered:
        return "google"
    return "web"


def parse_source_content(text: str, *, source: str, focus: str) -> dict[str, Any]:
    focus_set = {item.strip() for item in focus.split(",") if item.strip()}
    if focus_set & TOPIC_FOCUS_ALIASES:
        focus_set.add("topics")
    if "breaking_topics" in focus_set or "hashtags" in focus_set:
        focus_set.add("hashtags")

    topics: list[dict[str, Any]] = []
    if "culture" in focus_set:
        topics.extend(parse_culture_topics(text, source=source))
    if "topics" in focus_set:
        topics.extend(parse_general_topics(text, source=source))

    seen: set[str] = set()
    unique_topics: list[dict[str, Any]] = []
    for topic in topics:
        key = (topic.get("topic") or topic.get("key") or "").lower()
        if key and key not in seen:
            seen.add(key)
            unique_topics.append(topic)

    return {
        "source": source,
        "reel_formats": parse_reel_formats(text, source=source),
        "hashtags": parse_hashtags(text, source=source) if "hashtags" in focus_set or "niche" in focus_set else parse_hashtags(text, source=source)[:15],
        "topics": unique_topics[:25],
    }


def merge_parsed_results(parsed_pages: list[dict[str, Any]]) -> dict[str, Any]:
    format_seen: set[str] = set()
    tag_counter: Counter[str] = Counter()
    tag_sources: dict[str, set[str]] = {}
    topic_seen: set[str] = set()
    google_trends: list[dict[str, Any]] = []

    reel_formats: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []

    for page in parsed_pages:
        source = page.get("source") or "web"
        for fmt in page.get("reel_formats") or []:
            key = (fmt.get("name") or "").lower()
            if key and key not in format_seen:
                format_seen.add(key)
                reel_formats.append(fmt)
        for item in page.get("hashtags") or []:
            tag = item.get("hashtag") or item.get("tag")
            if not tag:
                continue
            tag_counter[tag] += int(item.get("post_count") or 1)
            tag_sources.setdefault(tag, set()).add(source)
        for topic in page.get("topics") or []:
            key = (topic.get("topic") or topic.get("key") or "").lower()
            if key and key not in topic_seen:
                topic_seen.add(key)
                topics.append(topic)
        for item in page.get("google_trends") or []:
            google_trends.append(item)

    hashtags = [
        {
            "hashtag": tag,
            "tag": tag,
            "post_count": count,
            "source_count": len(tag_sources.get(tag, set())),
            "sources": sorted(tag_sources.get(tag, set())),
        }
        for tag, count in tag_counter.most_common(30)
    ]

    trend_scores: list[dict[str, Any]] = []
    for idx, tag_item in enumerate(hashtags[:20]):
        tag = tag_item["tag"]
        trend_scores.append(
            {
                "group_type": "hashtag",
                "key": tag,
                "post_count": tag_item["post_count"],
                "source_count": tag_item["source_count"],
                "trend_score": round(100 - idx * 3 + tag_item["source_count"] * 5, 2),
            }
        )
    for idx, fmt in enumerate(reel_formats[:15]):
        trend_scores.append(
            {
                "group_type": "reel_format",
                "key": fmt.get("name"),
                "post_count": 1,
                "source": fmt.get("source"),
                "trend_score": round(80 - idx * 2, 2),
            }
        )
    for idx, topic in enumerate(topics[:10]):
        trend_scores.append(
            {
                "group_type": "topic",
                "key": topic.get("topic") or topic.get("key"),
                "post_count": 1,
                "source": topic.get("source"),
                "trend_score": round(70 - idx * 2, 2),
            }
        )
    for idx, item in enumerate(google_trends[:20]):
        traffic = int(item.get("traffic_score") or item.get("value_score") or 0)
        query_type = item.get("query_type") or "top"
        type_bonus = 3 if query_type == "rising" else 0
        trend_scores.append(
            {
                "group_type": "google_trend",
                "key": item.get("topic") or item.get("key"),
                "geo": item.get("geo"),
                "geo_label": item.get("geo_label"),
                "query_type": query_type,
                "approx_traffic": item.get("approx_traffic"),
                "traffic_score": traffic,
                "source": item.get("source") or "Google Trends",
                "trend_score": round(95 - idx * 2 + min(traffic // 100, 10) + type_bonus, 2),
                "news_items": item.get("news_items") or [],
                "explore_url": item.get("explore_url"),
            }
        )

    trend_scores.sort(key=lambda item: float(item.get("trend_score") or 0), reverse=True)

    source_breakdown = build_source_breakdown(parsed_pages)

    return {
        "reel_formats": reel_formats[:20],
        "hashtags": hashtags,
        "topics": topics,
        "google_trends": google_trends[:25],
        "trend_scores": trend_scores,
        "source_count": len(parsed_pages),
        "source_breakdown": source_breakdown,
    }


def attach_google_trends_by_country(merged: dict[str, Any], by_country: dict[str, Any]) -> dict[str, Any]:
    if not by_country:
        return merged
    from agents.trend.services.google_trend_fetcher import build_queries_by_country

    top_by_country, rising_by_country = build_queries_by_country(by_country)
    return {
        **merged,
        "google_trends_by_country": by_country,
        "top_queries_by_country": top_by_country,
        "rising_queries_by_country": rising_by_country,
    }


def filter_for_niche(merged: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    if not keywords:
        return merged
    targets = [kw.lower() for kw in keywords if kw]

    def matches(text: str) -> bool:
        lowered = (text or "").lower()
        return any(kw in lowered for kw in targets)

    filtered = {
        **merged,
        "hashtags": [
            item
            for item in merged.get("hashtags") or []
            if matches(item.get("hashtag") or item.get("tag") or "")
        ],
        "reel_formats": [
            item
            for item in merged.get("reel_formats") or []
            if matches(item.get("name") or "")
        ],
        "topics": [
            item
            for item in merged.get("topics") or []
            if matches(item.get("topic") or item.get("key") or "")
        ],
        "google_trends": [
            item
            for item in merged.get("google_trends") or []
            if matches(item.get("topic") or item.get("key") or "")
        ],
    }
    if not filtered["hashtags"]:
        filtered["hashtags"] = (merged.get("hashtags") or [])[:10]
    if not filtered["reel_formats"]:
        filtered["reel_formats"] = (merged.get("reel_formats") or [])[:8]
    if not filtered["topics"]:
        filtered["topics"] = (merged.get("topics") or [])[:5]
    if not filtered["google_trends"]:
        filtered["google_trends"] = (merged.get("google_trends") or [])[:10]
    filtered["trend_scores"] = merge_parsed_results(
        [{
            "source": "filtered",
            **{k: filtered.get(k) for k in ("reel_formats", "hashtags", "topics", "google_trends")},
        }]
    ).get("trend_scores", [])
    return filtered
