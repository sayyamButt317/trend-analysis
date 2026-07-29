import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from agents.trend.services.web_trend_parser import parse_google_trends_page
from agents.trend.services.web_trend_sources import (
    GOOGLE_TRENDS_GEOS,
    GOOGLE_TRENDS_RSS_URL,
    resolve_geos_for_region,
)

logger = logging.getLogger(__name__)

HT_NS = {"ht": "https://trends.google.com/trending/rss"}


def _parse_traffic(value: str | None) -> int:
    if not value:
        return 0
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else 0


def _parse_rss(xml_text: str, *, geo: str, label: str) -> list[dict[str, Any]]:
    trends: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse Google Trends RSS for geo=%s", geo)
        return trends

    for item in root.findall(".//item"):
        title_el = item.find("title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title or title.lower() == "daily search trends":
            continue

        traffic_el = item.find("ht:approx_traffic", HT_NS)
        pub_el = item.find("pubDate")
        news_items: list[dict[str, str]] = []
        for news in item.findall("ht:news_item", HT_NS):
            news_title = news.find("ht:news_item_title", HT_NS)
            news_url = news.find("ht:news_item_url", HT_NS)
            news_source = news.find("ht:news_item_source", HT_NS)
            if news_title is not None and (news_title.text or "").strip():
                news_items.append(
                    {
                        "title": news_title.text.strip(),
                        "url": (news_url.text or "").strip() if news_url is not None else "",
                        "source": (news_source.text or "").strip() if news_source is not None else "",
                    }
                )

        trends.append(
            {
                "topic": title,
                "key": title,
                "geo": geo,
                "geo_label": label,
                "approx_traffic": (traffic_el.text or "").strip() if traffic_el is not None else None,
                "traffic_score": _parse_traffic(traffic_el.text if traffic_el is not None else None),
                "published_at": (pub_el.text or "").strip() if pub_el is not None else None,
                "news_items": news_items[:3],
                "source": f"Google Trends ({label})",
                "type": "google_trend",
            }
        )
    return trends


async def _fetch_geo_rss(geo: str, label: str) -> list[dict[str, Any]]:
    url = GOOGLE_TRENDS_RSS_URL.format(geo=geo)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TrendBot/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return _parse_rss(response.text, geo=geo, label=label)
    except Exception:
        logger.warning("Google Trends RSS fetch failed for geo=%s", geo, exc_info=True)
        return []


async def fetch_google_trends(*, region: str | None = None) -> dict[str, Any]:
    """
    Fetch daily trending searches from Google Trends RSS.
    Uses region to pick geo(s); defaults to US + UAE + SA + UK + PK.
    """
    geo_codes = resolve_geos_for_region(region)
    geo_labels = {item["geo"]: item["label"] for item in GOOGLE_TRENDS_GEOS}

    tasks = [
        _fetch_geo_rss(geo, geo_labels.get(geo, geo))
        for geo in geo_codes
    ]
    results = await asyncio.gather(*tasks)

    all_trends: list[dict[str, Any]] = []
    seen: set[str] = set()
    for batch in results:
        for trend in batch:
            key = (trend.get("topic") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            all_trends.append(trend)

    all_trends.sort(key=lambda item: item.get("traffic_score") or 0, reverse=True)

    parsed_page = parse_google_trends_page(all_trends) if all_trends else None

    return {
        "success": bool(all_trends),
        "geo_codes": geo_codes,
        "trend_count": len(all_trends),
        "trends": all_trends,
        "parsed_page": parsed_page,
        "sources": [f"Google Trends ({geo_labels.get(g, g)})" for g in geo_codes],
    }
