import re
from collections import Counter
from typing import Any
from agents.trend.Nodes.common import GENERIC_HASHTAGS

SONG_LINE_RE = re.compile(
    r"^#{1,3}\s*#?\d+\.?\s*(.+?)\s*[–—-]\s*(.+?)\s*$",
    re.MULTILINE,
)
TREND_HEADER_RE = re.compile(
    r"^#{2,3}\s*\*{0,2}(.+?)\*{0,2}\s*$",
    re.MULTILINE,
)
HASHTAG_RE = re.compile(r"#([A-Za-z][A-Za-z0-9_]{2,49})")
QUOTED_TREND_RE = re.compile(r"[\"“]([^\"”]{3,80})[\"”]\s+trend", re.IGNORECASE)

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
        "how to find trending songs",
        "references",
        "see also",
        "origin and spread",
        "reception",
        "product",
        "pricing",
        "resources",
    }
)


def _clean_header(text: str) -> str:
    cleaned = re.sub(r"\*{1,2}", "", text or "").strip()
    cleaned = re.sub(r"^\(\w+ \d+, \d{4}\)\s*", "", cleaned)
    return cleaned.strip(" .")


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def parse_songs(text: str, *, source: str) -> list[dict[str, Any]]:
    songs: list[dict[str, Any]] = []
    for match in SONG_LINE_RE.finditer(text):
        title = re.sub(r"\s*\[\.\.\.\].*$", "", match.group(1).strip().strip("*"))
        artist = re.sub(r"\s*\[\.\.\.\].*$", "", match.group(2).strip().strip("*"))
        title = re.split(r"\s*#+\s*", title)[0].strip()
        artist = re.split(r"\s*#+\s*", artist)[0].strip()
        if len(title) < 2 or len(title) > 80:
            continue
        songs.append(
            {
                "title": title,
                "artist": artist,
                "label": f"{title} – {artist}",
                "source": source,
                "type": "song",
            }
        )
    return songs


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
        "songs": [],
        "reel_formats": [],
        "hashtags": [],
        "topics": topics,
        "google_trends": trends,
    }


def parse_source_content(text: str, *, source: str, focus: str) -> dict[str, Any]:
    focus_set = {item.strip() for item in focus.split(",")}
    return {
        "source": source,
        "songs": parse_songs(text, source=source) if "songs" in focus_set or "audio" in focus_set else [],
        "reel_formats": parse_reel_formats(text, source=source),
        "hashtags": parse_hashtags(text, source=source) if "hashtags" in focus_set or "niche" in focus_set else parse_hashtags(text, source=source)[:15],
        "topics": parse_culture_topics(text, source=source) if "culture" in focus_set or "topics" in focus_set else [],
    }


def merge_parsed_results(parsed_pages: list[dict[str, Any]]) -> dict[str, Any]:
    song_seen: set[str] = set()
    format_seen: set[str] = set()
    tag_counter: Counter[str] = Counter()
    tag_sources: dict[str, set[str]] = {}
    topic_seen: set[str] = set()
    google_trends: list[dict[str, Any]] = []

    songs: list[dict[str, Any]] = []
    reel_formats: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []

    for page in parsed_pages:
        source = page.get("source") or "web"
        for song in page.get("songs") or []:
            key = (song.get("label") or "").lower()
            if key and key not in song_seen:
                song_seen.add(key)
                songs.append(song)
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
        traffic = int(item.get("traffic_score") or 0)
        trend_scores.append(
            {
                "group_type": "google_trend",
                "key": item.get("topic") or item.get("key"),
                "geo": item.get("geo"),
                "approx_traffic": item.get("approx_traffic"),
                "traffic_score": traffic,
                "source": item.get("source") or "Google Trends",
                "trend_score": round(95 - idx * 2 + min(traffic // 100, 10), 2),
                "news_items": item.get("news_items") or [],
            }
        )

    trend_scores.sort(key=lambda item: float(item.get("trend_score") or 0), reverse=True)

    return {
        "songs": songs[:15],
        "reel_formats": reel_formats[:20],
        "hashtags": hashtags,
        "topics": topics,
        "google_trends": google_trends[:25],
        "trend_scores": trend_scores,
        "source_count": len(parsed_pages),
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
        "songs": merged.get("songs") or [],
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
            **{k: filtered.get(k) for k in ("songs", "reel_formats", "hashtags", "topics", "google_trends")},
        }]
    ).get("trend_scores", [])
    return filtered
