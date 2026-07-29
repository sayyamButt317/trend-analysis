import asyncio
from collections import Counter
from typing import Any
from fastapi import HTTPException
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

AGENT_TYPE = "trend"


def _trends_table() -> str:
    return (config.SUPABASE_TABLE_TRENDS or "trends").strip()


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _ensure_storage_configured() -> None:
    if not _is_storage_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase is not configured. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY in .env."
            ),
        )


def _fetch_trends_sync(
    trend_id: str | None = None,
    *,
    full: bool = False,
) -> list[dict[str, Any]]:
    client = get_supabase()
    columns = (
        "*"
        if full
        else (
            "id,created_at,success,status,platform,country,category,summary,"
            "post_count,viral_post_count,discovery_source,duration_sec,error"
        )
    )
    query = (
        client.table(_trends_table())
        .select(columns)
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
    )
    if trend_id:
        query = query.eq("id", trend_id)

    response = query.execute()
    rows = response.data or []
    if trend_id and not rows:
        raise HTTPException(status_code=404, detail=f"Trend run not found: {trend_id}")
    return rows


def _trend_overview_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trend_id": str(row.get("id")),
        "created_at": row.get("created_at"),
        "success": row.get("success"),
        "status": row.get("status"),
        "platform": row.get("platform"),
        "country": row.get("country"),
        "category": row.get("category"),
        "discovery_source": row.get("discovery_source"),
        "post_count": int(row.get("post_count") or 0),
        "viral_post_count": int(row.get("viral_post_count") or 0),
        "duration_sec": row.get("duration_sec"),
        "summary": row.get("summary"),
    }


def _collect_hashtags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tag_counts: Counter[str] = Counter()
    by_run: list[dict[str, Any]] = []

    for row in rows:
        run_counter: Counter[str] = Counter()
        for item in row.get("hashtags") or []:
            tag = str(item.get("hashtag") or item.get("tag") or "").strip().lstrip("#").lower()
            count = int(item.get("post_count") or item.get("count") or 1)
            if not tag:
                continue
            tag_counts[tag] += count
            run_counter[tag] += count

        if run_counter:
            by_run.append(
                {
                    "trend_id": str(row.get("id")),
                    "created_at": row.get("created_at"),
                    "country": row.get("country"),
                    "category": row.get("category"),
                    "hashtags": [
                        {"tag": tag, "count": count}
                        for tag, count in run_counter.most_common()
                    ],
                }
            )

    return {
        "total_unique": len(tag_counts),
        "hashtags": [
            {"tag": tag, "count": count} for tag, count in tag_counts.most_common()
        ],
        "by_run": by_run,
    }


def _build_analytics_payload(
    row: dict[str, Any],
    *,
    recent_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = row.get("result") or {}
    trend_scores = row.get("trend_scores") or result.get("trend_scores") or []
    viral_posts = row.get("viral_posts") or result.get("viral_posts") or []
    hashtags = row.get("hashtags") or result.get("hashtags") or []
    topics = row.get("topics") or result.get("topics") or []
    influencers = row.get("discovered_influencers") or result.get("discovered_influencers") or []

    top_hashtags = [
        {
            "tag": item.get("hashtag") or item.get("tag"),
            "count": item.get("post_count") or item.get("count"),
            "creator_count": item.get("creator_count"),
        }
        for item in hashtags[:15]
    ]

    competitor_insights = row.get("competitor_strategies") or result.get("competitor_strategies")
    market = row.get("market_insights") or result.get("market_insights") or {}
    company = (
        row.get("company")
        or result.get("company")
        or (row.get("config") or {}).get("company")
        or {}
    )

    return {
        "trend_id": str(row.get("id")),
        "overview": {
            "company_name": (company or {}).get("name") if isinstance(company, dict) else None,
            "detected_category": (company or {}).get("detected_category") if isinstance(company, dict) else row.get("category"),
            "region": (company or {}).get("region") if isinstance(company, dict) else None,
            "platform": row.get("platform"),
            "country": row.get("country"),
            "category": row.get("category"),
            "discovery_source": row.get("discovery_source"),
            "post_count": int(row.get("post_count") or 0),
            "viral_post_count": int(row.get("viral_post_count") or 0),
            "status": row.get("status"),
            "success": row.get("success"),
            "created_at": row.get("created_at"),
            "duration_sec": row.get("duration_sec"),
            "summary": row.get("summary") or result.get("trend_summary"),
        },
        "trend_scores": trend_scores[:20],
        "viral_posts": viral_posts[:20],
        "viral_sounds": row.get("viral_sounds") or result.get("viral_sounds") or [],
        "viral_categories": row.get("viral_categories") or result.get("viral_categories") or [],
        "hashtags": {
            "total_unique": len(hashtags),
            "top_hashtags": top_hashtags,
        },
        "topics": topics,
        "discovered_influencers": influencers,
        "audio_summary": row.get("audio_summary") or result.get("audio_summary") or [],
        "competitor_strategies": competitor_insights,
        "market_insights": market,
        "recent_runs": recent_runs or [],
    }


async def list_stored_trends() -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await asyncio.to_thread(_fetch_trends_sync, None, full=False)
    return {
        "success": True,
        "count": len(rows),
        "trends": [_trend_overview_item(row) for row in rows],
    }


async def get_stored_trend(trend_id: str) -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await asyncio.to_thread(_fetch_trends_sync, trend_id, full=True)
    row = rows[0]
    return {
        "success": True,
        "trend": row,
    }


async def get_trend_analytics(trend_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await asyncio.to_thread(_fetch_trends_sync, trend_id, full=True)

    if not rows:
        return {
            "success": True,
            "trend_id": trend_id,
            "message": "No trend data found. Run POST /trend-analysis/discover first.",
            "overview": None,
            "trend_scores": [],
            "viral_posts": [],
            "hashtags": None,
            "recent_runs": [],
        }

    recent = [_trend_overview_item(row) for row in rows[:10]]
    target = rows[0]

    return {
        "success": True,
        **_build_analytics_payload(target, recent_runs=recent),
    }


async def list_stored_trend_hashtags(trend_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await asyncio.to_thread(_fetch_trends_sync, trend_id, full=True)
    hashtag_data = _collect_hashtags(rows)

    return {
        "success": True,
        "trend_id": trend_id,
        "run_count": len(rows),
        **hashtag_data,
    }


async def list_stored_viral_posts(trend_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await asyncio.to_thread(_fetch_trends_sync, trend_id, full=True)

    viral_posts: list[dict[str, Any]] = []
    for row in rows:
        result = row.get("result") or {}
        for post in row.get("viral_posts") or result.get("viral_posts") or []:
            viral_posts.append(
                {
                    "trend_id": str(row.get("id")),
                    "created_at": row.get("created_at"),
                    "country": row.get("country"),
                    "category": row.get("category"),
                    **post,
                }
            )

    viral_posts.sort(
        key=lambda item: float(item.get("engagement_rate") or item.get("virality_score") or 0),
        reverse=True,
    )

    return {
        "success": True,
        "trend_id": trend_id,
        "run_count": len(rows),
        "count": len(viral_posts),
        "viral_posts": viral_posts,
    }


async def list_stored_trend_scores(trend_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await asyncio.to_thread(_fetch_trends_sync, trend_id, full=True)

    scores: list[dict[str, Any]] = []
    for row in rows:
        result = row.get("result") or {}
        for item in row.get("trend_scores") or result.get("trend_scores") or []:
            scores.append(
                {
                    "trend_id": str(row.get("id")),
                    "created_at": row.get("created_at"),
                    "country": row.get("country"),
                    "category": row.get("category"),
                    **item,
                }
            )

    scores.sort(key=lambda item: float(item.get("trend_score") or 0), reverse=True)

    return {
        "success": True,
        "trend_id": trend_id,
        "run_count": len(rows),
        "count": len(scores),
        "trend_scores": scores,
    }
