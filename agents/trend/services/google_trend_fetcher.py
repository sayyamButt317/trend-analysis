import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx

from agents.trend.services.web_trend_parser import parse_google_trends_page
from agents.trend.services.web_trend_sources import (
    DEFAULT_GOOGLE_TREND_GEOS,
    GOOGLE_TRENDS_GEOS,
    GOOGLE_TRENDS_RSS_URL,
    GOOGLE_TREND_GEO_LABELS,
    resolve_geos_for_region,
)

logger = logging.getLogger(__name__)

HT_NS = {"ht": "https://trends.google.com/trending/rss"}
GT_JSON_PREFIX = ")]}',"
EXPLORE_URL = "https://trends.google.com/trends/api/explore"
WIDGET_URL = "https://trends.google.com/trends/api/widgetdata/relatedsearches"
EXPLORE_SEED_KEYWORDS = ("instagram", "social media")
EXPLORE_REQUEST_DELAY_SEC = 3.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_traffic(value: str | None) -> int:
    if not value:
        return 0
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else 0


def _parse_gt_json(text: str) -> dict[str, Any]:
    payload = text.strip()
    if payload.startswith(GT_JSON_PREFIX):
        payload = payload[len(GT_JSON_PREFIX) :]
    return json.loads(payload)


def _trend_item(
    *,
    query: str,
    geo: str,
    label: str,
    query_type: str,
    approx_traffic: str | None = None,
    traffic_score: int = 0,
    published_at: str | None = None,
    news_items: list[dict[str, str]] | None = None,
    seed_keyword: str | None = None,
    value_score: int | None = None,
    formatted_value: str | None = None,
    explore_url: str | None = None,
) -> dict[str, Any]:
    return {
        "topic": query,
        "key": query,
        "query": query,
        "geo": geo,
        "geo_label": label,
        "query_type": query_type,
        "approx_traffic": approx_traffic,
        "traffic_score": traffic_score,
        "value_score": value_score,
        "formatted_value": formatted_value,
        "published_at": published_at,
        "news_items": news_items or [],
        "seed_keyword": seed_keyword,
        "explore_url": explore_url or f"https://trends.google.com/explore?geo={geo}&q={quote(query)}",
        "source": f"Google Trends ({label})",
        "type": "google_trend",
    }


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
        traffic_raw = (traffic_el.text or "").strip() if traffic_el is not None else None
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
            _trend_item(
                query=title,
                geo=geo,
                label=label,
                query_type="top",
                approx_traffic=traffic_raw,
                traffic_score=_parse_traffic(traffic_raw),
                published_at=(pub_el.text or "").strip() if pub_el is not None else None,
                news_items=news_items[:3],
                explore_url=f"https://trends.google.com/explore?geo={geo}&q={quote(title)}",
            )
        )
    return trends


def _split_top_and_rising_from_rss(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use RSS traffic + news velocity as rising proxy when Explore API is unavailable."""
    if not items:
        return [], []

    ranked = sorted(items, key=lambda item: item.get("traffic_score") or 0, reverse=True)
    top_queries = [{**item, "query_type": "top"} for item in ranked[:10]]

    rising_candidates: list[dict[str, Any]] = []
    for item in ranked[3:15]:
        news_count = len(item.get("news_items") or [])
        traffic = int(item.get("traffic_score") or 0)
        if news_count >= 1 or traffic > 0:
            rising_candidates.append(
                {
                    **item,
                    "query_type": "rising",
                    "rising_score": news_count * 10 + min(traffic // 1000, 50),
                }
            )
    rising_candidates.sort(key=lambda item: item.get("rising_score") or 0, reverse=True)
    rising_queries = rising_candidates[:10]
    return top_queries, rising_queries


def _parse_related_widget(payload: dict[str, Any], *, geo: str, label: str, seed: str) -> tuple[list[dict], list[dict]]:
    top_items: list[dict[str, Any]] = []
    rising_items: list[dict[str, Any]] = []
    ranked_lists = payload.get("default", {}).get("rankedList") or []
    for idx, ranked in enumerate(ranked_lists):
        query_type = "top" if idx == 0 else "rising"
        for entry in ranked.get("rankedKeyword") or []:
            query = (entry.get("query") or "").strip()
            if not query:
                continue
            value = int(entry.get("value") or 0)
            item = _trend_item(
                query=query,
                geo=geo,
                label=label,
                query_type=query_type,
                seed_keyword=seed,
                value_score=value,
                formatted_value=entry.get("formattedValue"),
                explore_url=f"https://trends.google.com/explore?geo={geo}&q={quote(query)}",
            )
            if query_type == "top":
                top_items.append(item)
            else:
                rising_items.append(item)
    return top_items, rising_items


async def _fetch_geo_rss(geo: str, label: str) -> list[dict[str, Any]]:
    url = GOOGLE_TRENDS_RSS_URL.format(geo=geo)
    headers = {
        **HEADERS,
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


async def _fetch_explore_related(
    client: httpx.AsyncClient,
    *,
    geo: str,
    label: str,
    seed_keyword: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    req = {
        "comparisonItem": [{"keyword": seed_keyword, "geo": geo, "time": "now 7-d"}],
        "category": 0,
        "property": "",
    }
    req_param = quote(json.dumps(req, separators=(",", ":")))
    explore_headers = {
        **HEADERS,
        "Referer": f"https://trends.google.com/explore?geo={geo}&q={quote(seed_keyword)}",
    }
    try:
        explore_resp = await client.get(
            f"{EXPLORE_URL}?hl=en-US&tz=300&req={req_param}",
            headers=explore_headers,
        )
        if explore_resp.status_code == 429:
            logger.info("Google Trends Explore rate-limited for geo=%s seed=%s", geo, seed_keyword)
            return [], []
        explore_resp.raise_for_status()
        explore_data = _parse_gt_json(explore_resp.text)
        widget = next((w for w in explore_data.get("widgets") or [] if w.get("id") == "RELATED_QUERIES"), None)
        if not widget:
            return [], []

        widget_req = quote(json.dumps(widget.get("request") or req, separators=(",", ":")))
        token = quote(widget.get("token") or "")
        widget_resp = await client.get(
            f"{WIDGET_URL}?hl=en-US&tz=300&req={widget_req}&token={token}",
            headers=explore_headers,
        )
        if widget_resp.status_code == 429:
            return [], []
        widget_resp.raise_for_status()
        return _parse_related_widget(
            _parse_gt_json(widget_resp.text),
            geo=geo,
            label=label,
            seed=seed_keyword,
        )
    except Exception:
        logger.debug(
            "Google Trends explore related queries failed for geo=%s seed=%s",
            geo,
            seed_keyword,
            exc_info=True,
        )
        return [], []


async def _fetch_country_trends(geo: str, label: str) -> dict[str, Any]:
    rss_items = await _fetch_geo_rss(geo, label)
    rss_top, rss_rising = _split_top_and_rising_from_rss(rss_items)

    explore_top: list[dict[str, Any]] = []
    explore_rising: list[dict[str, Any]] = []
    explore_available = False

    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
        for seed in EXPLORE_SEED_KEYWORDS:
            await asyncio.sleep(EXPLORE_REQUEST_DELAY_SEC)
            top_batch, rising_batch = await _fetch_explore_related(
                client,
                geo=geo,
                label=label,
                seed_keyword=seed,
            )
            if top_batch or rising_batch:
                explore_available = True
            explore_top.extend(top_batch)
            explore_rising.extend(rising_batch)

    def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            key = (item.get("query") or item.get("topic") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    top_queries = _dedupe(explore_top + rss_top)
    rising_queries = _dedupe(explore_rising + rss_rising)

    if not top_queries and rss_items:
        top_queries = [{**item, "query_type": "top"} for item in rss_items[:10]]
    if not rising_queries and rss_rising:
        rising_queries = rss_rising

    all_items = _dedupe(top_queries + rising_queries)

    return {
        "geo": geo,
        "label": label,
        "explore_url": f"https://trends.google.com/explore?geo={geo}",
        "trending_url": f"https://trends.google.com/trending?geo={geo}",
        "top_queries": top_queries[:15],
        "rising_queries": rising_queries[:15],
        "all_queries": all_items[:25],
        "explore_api_available": explore_available,
        "top_count": len(top_queries),
        "rising_count": len(rising_queries),
    }


def _empty_country_entry(geo: str) -> dict[str, Any]:
    label = GOOGLE_TREND_GEO_LABELS.get(geo, geo)
    return {
        "geo": geo,
        "label": label,
        "explore_url": f"https://trends.google.com/explore?geo={geo}",
        "trending_url": f"https://trends.google.com/trending?geo={geo}",
        "top_queries": [],
        "rising_queries": [],
        "all_queries": [],
        "explore_api_available": False,
        "top_count": 0,
        "rising_count": 0,
    }


def build_queries_by_country(by_country: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return top_queries and rising_queries keyed by country label."""
    top_by_country: dict[str, Any] = {}
    rising_by_country: dict[str, Any] = {}
    for geo in DEFAULT_GOOGLE_TREND_GEOS:
        entry = by_country.get(geo) or _empty_country_entry(geo)
        label = entry.get("label") or GOOGLE_TREND_GEO_LABELS.get(geo, geo)
        top_by_country[label] = {
            "geo": geo,
            "country": label,
            "queries": entry.get("top_queries") or [],
            "count": entry.get("top_count") or len(entry.get("top_queries") or []),
            "explore_url": entry.get("explore_url"),
            "trending_url": entry.get("trending_url"),
        }
        rising_by_country[label] = {
            "geo": geo,
            "country": label,
            "queries": entry.get("rising_queries") or [],
            "count": entry.get("rising_count") or len(entry.get("rising_queries") or []),
            "explore_url": entry.get("explore_url"),
            "trending_url": entry.get("trending_url"),
        }
    return top_by_country, rising_by_country


async def fetch_google_trends(*, region: str | None = None) -> dict[str, Any]:
    """
    Fetch Google Trends per country:
    - top_queries: daily trending searches (RSS) + Explore related-top
    - rising_queries: Explore related-rising + RSS breakout heuristic
    """
    geo_codes = resolve_geos_for_region(region)
    geo_labels = {item["geo"]: item["label"] for item in GOOGLE_TRENDS_GEOS}

    country_results = await asyncio.gather(
        *[_fetch_country_trends(geo, geo_labels.get(geo, geo)) for geo in geo_codes]
    )

    by_country: dict[str, dict[str, Any]] = {
        entry["geo"]: entry for entry in country_results if entry.get("geo")
    }
    for geo in geo_codes:
        if geo not in by_country:
            by_country[geo] = _empty_country_entry(geo)

    top_queries_by_country, rising_queries_by_country = build_queries_by_country(by_country)

    all_trends: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in country_results:
        for bucket in ("top_queries", "rising_queries"):
            for trend in entry.get(bucket) or []:
                key = f"{trend.get('geo')}:{(trend.get('query') or '').lower()}:{trend.get('query_type')}"
                if key in seen:
                    continue
                seen.add(key)
                all_trends.append(trend)

    all_trends.sort(key=lambda item: item.get("traffic_score") or item.get("value_score") or 0, reverse=True)
    parsed_page = parse_google_trends_page(all_trends) if all_trends else None

    return {
        "success": bool(all_trends),
        "geo_codes": geo_codes,
        "trend_count": len(all_trends),
        "trends": all_trends,
        "google_trends_by_country": by_country,
        "top_queries_by_country": top_queries_by_country,
        "rising_queries_by_country": rising_queries_by_country,
        "parsed_page": parsed_page,
        "sources": [f"Google Trends ({geo_labels.get(g, g)})" for g in geo_codes],
    }
