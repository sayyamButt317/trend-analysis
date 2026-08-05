import asyncio
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase
from db.report_storage import fetch_stored_reports, save_competitor_report as persist_report
from db.competitor_storage import delete_competitor_analysis

AGENT_TYPE = "competitor"


def _analysis_table() -> str:
    return (config.SUPABASE_TABLE_ANALYSIS or "analysis").strip()


def _prompts_table() -> str:
    return (config.SUPABASE_TABLE_PROMPTS or "prompts").strip()


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _fetch_analyses_sync(analysis_id: str | None = None) -> list[dict[str, Any]]:
    client = get_supabase()
    query = (
        client.table(_analysis_table())
        .select("id,prompt_id,created_at,success,result")
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
    )
    if analysis_id:
        query = query.eq("id", analysis_id)

    response = query.execute()
    rows = response.data or []
    if analysis_id and not rows:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")
    return rows


def _fetch_prompt_sync(prompt_id: str) -> dict[str, Any] | None:
    client = get_supabase()
    response = (
        client.table(_prompts_table())
        .select("id,region,company_name,company_data,competitors,created_at")
        .eq("id", prompt_id)
        .maybe_single()
        .execute()
    )
    return response.data


def _ensure_storage_configured() -> None:
    if not _is_storage_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase is not configured. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY in .env."
            ),
        )


def _competitor_summary(
    competitor: dict[str, Any],
    *,
    analysis_id: str,
    prompt_id: str,
    created_at: str | None,
    company_name: str | None,
) -> dict[str, Any]:
    posts = competitor.get("posts") or []
    return {
        "analysis_id": analysis_id,
        "prompt_id": prompt_id,
        "created_at": created_at,
        "company_name": company_name,
        "username": competitor.get("username"),
        "name": competitor.get("name"),
        "followers": competitor.get("followers"),
        "profile_url": competitor.get("profile_url"),
        "profile_picture_url": competitor.get("profile_picture_url"),
        "image_url": competitor.get("image_url"),
        "bio": competitor.get("bio"),
        "website": competitor.get("website"),
        "discovered_by": competitor.get("discovered_by"),
        "match_score": competitor.get("match_score"),
        "match_reasons": competitor.get("match_reasons") or [],
        "content_strategy": competitor.get("content_strategy") or {},
        "post_count": len(posts),
    }


def _flatten_content(analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for row in analyses:
        result = row.get("result") or {}
        analysis_id = str(row.get("id"))
        prompt_id = str(row.get("prompt_id"))
        created_at = row.get("created_at")
        company_name = (result.get("company") or {}).get("name")

        for competitor in result.get("competitors") or []:
            username = competitor.get("username")
            competitor_name = competitor.get("name")
            for post in competitor.get("posts") or []:
                content.append(
                    {
                        "analysis_id": analysis_id,
                        "prompt_id": prompt_id,
                        "created_at": created_at,
                        "company_name": company_name,
                        "username": username,
                        "competitor_name": competitor_name,
                        "id": post.get("id"),
                        "caption": post.get("caption"),
                        "media_type": post.get("media_type"),
                        "media_url": post.get("media_url"),
                        "thumbnail_url": post.get("thumbnail_url"),
                        "permalink": post.get("permalink"),
                        "timestamp": post.get("timestamp"),
                        "likes": post.get("likes"),
                        "comments": post.get("comments"),
                        "engagement_rate": post.get("engagement_rate"),
                        "hashtags": post.get("hashtags") or [],
                    }
                )
    return content


def _collect_hashtags(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    tag_counts: Counter[str] = Counter()
    by_analysis: list[dict[str, Any]] = []

    for row in analyses:
        result = row.get("result") or {}
        analysis_id = str(row.get("id"))
        analysis_counter: Counter[str] = Counter()

        for competitor in result.get("competitors") or []:
            for post in competitor.get("posts") or []:
                for tag in post.get("hashtags") or []:
                    normalized = str(tag).strip().lstrip("#").lower()
                    if not normalized:
                        continue
                    tag_counts[normalized] += 1
                    analysis_counter[normalized] += 1

        if analysis_counter:
            by_analysis.append(
                {
                    "analysis_id": analysis_id,
                    "prompt_id": str(row.get("prompt_id")),
                    "created_at": row.get("created_at"),
                    "company_name": (result.get("company") or {}).get("name"),
                    "hashtags": [
                        {"tag": tag, "count": count}
                        for tag, count in analysis_counter.most_common()
                    ],
                }
            )

    return {
        "total_unique": len(tag_counts),
        "hashtags": [
            {"tag": tag, "count": count} for tag, count in tag_counts.most_common()
        ],
        "by_analysis": by_analysis,
    }


def _top_posts(result: dict[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for competitor in result.get("competitors") or []:
        username = competitor.get("username")
        competitor_name = competitor.get("name")
        for post in competitor.get("posts") or []:
            posts.append(
                {
                    "username": username,
                    "competitor_name": competitor_name,
                    "id": post.get("id"),
                    "caption": post.get("caption"),
                    "media_type": post.get("media_type"),
                    "media_url": post.get("media_url"),
                    "thumbnail_url": post.get("thumbnail_url"),
                    "permalink": post.get("permalink"),
                    "timestamp": post.get("timestamp"),
                    "likes": post.get("likes"),
                    "comments": post.get("comments"),
                    "engagement_rate": post.get("engagement_rate"),
                    "hashtags": post.get("hashtags") or [],
                }
            )
    posts.sort(key=lambda item: float(item.get("engagement_rate") or 0), reverse=True)
    return posts[:limit]


def _build_recommendations(result: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    market = result.get("market_insights") or {}
    content_usage = market.get("content_usage") or {}

    if content_usage.get("summary"):
        recommendations.append(content_usage["summary"])

    most_used_format = content_usage.get("most_used_format")
    if most_used_format:
        recommendations.append(
            f"Most competitors publish {most_used_format} content — prioritize this format in your strategy."
        )

    most_used_category = content_usage.get("most_used_category")
    if most_used_category:
        recommendations.append(
            f"The most common content category is {most_used_category} — create more posts in this area."
        )

    for insight in content_usage.get("insights") or []:
        if insight not in recommendations:
            recommendations.append(str(insight))

    dominant_types = market.get("dominant_content_types") or []
    if dominant_types and not most_used_format:
        top = dominant_types[0]
        recommendations.append(
            f"Market leaders favor {top['type']} ({top['count']} posts analyzed)."
        )

    top_tags = market.get("top_hashtags") or []
    if top_tags:
        tags = ", ".join(f"#{item['tag']}" for item in top_tags[:5])
        recommendations.append(f"Consider using these market hashtags: {tags}.")

    return recommendations


def _build_report(row: dict[str, Any], prompt: dict[str, Any] | None) -> dict[str, Any]:
    result = row.get("result") or {}
    company = result.get("company") or {}
    company_name = company.get("name") or (prompt or {}).get("company_name") or "Unknown Company"
    filters = result.get("filters_applied") or {}
    meta = result.get("meta") or {}
    market = result.get("market_insights") or {}
    hashtag_data = _collect_hashtags([row])

    competitors = [
        _competitor_summary(
            competitor,
            analysis_id=str(row.get("id")),
            prompt_id=str(row.get("prompt_id")),
            created_at=row.get("created_at"),
            company_name=company_name,
        )
        for competitor in result.get("competitors") or []
    ]

    return {
        "report_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_id": str(row.get("id")),
        "prompt_id": str(row.get("prompt_id")),
        "analysis_created_at": row.get("created_at"),
        "title": f"Competitor Analysis Report: {company_name}",
        "input": {
            "region": (prompt or {}).get("region") or filters.get("region"),
            "company_name": company_name,
            "requested_competitors": (prompt or {}).get("competitors") or [],
            "prompt_created_at": (prompt or {}).get("created_at"),
        },
        "executive_summary": result.get("summary") or row.get("summary"),
        "company": company,
        "filters_applied": filters,
        "matching_mode": result.get("matching_mode"),
        "discovery_warnings": result.get("discovery_warnings") or [],
        "stats": {
            "success": bool(result.get("success")),
            "status": meta.get("status"),
            "platform": meta.get("platform") or "instagram",
            "competitor_count": int(result.get("competitor_count") or len(competitors)),
            "post_count": int(result.get("post_count") or 0),
            "duration_sec": meta.get("duration_sec") or row.get("duration_sec"),
        },
        "market_insights": market,
        "competitors": competitors,
        "content": {
            "total_posts": int(result.get("post_count") or 0),
            "top_posts": _top_posts(result),
        },
        "hashtags": {
            "total_unique": hashtag_data["total_unique"],
            "top_hashtags": hashtag_data["hashtags"][:20],
        },
        "recommendations": _build_recommendations(result),
    }


def _report_list_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_id": str(row.get("id")),
        "analysis_id": str(row.get("analysis_id")),
        "prompt_id": str(row.get("prompt_id")),
        "title": row.get("title"),
        "company_name": row.get("company_name"),
        "region": row.get("region"),
        "executive_summary": row.get("executive_summary"),
        "competitor_count": row.get("competitor_count"),
        "post_count": row.get("post_count"),
        "created_at": row.get("created_at"),
    }


async def create_competitor_report(analysis_id: str) -> dict[str, Any]:
    _ensure_storage_configured()
    analyses = await asyncio.to_thread(_fetch_analyses_sync, analysis_id)
    row = analyses[0]
    prompt_id = str(row.get("prompt_id"))
    prompt = await asyncio.to_thread(_fetch_prompt_sync, prompt_id)

    report_id = str(uuid.uuid4())
    report = _build_report(row, prompt)
    report["report_id"] = report_id

    try:
        await persist_report(
            report_id=report_id,
            analysis_id=analysis_id,
            prompt_id=prompt_id,
            report=report,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save report: {exc}") from exc

    return {
        "success": True,
        "report_id": report_id,
        "analysis_id": analysis_id,
        "report": report,
    }


async def get_stored_report(report_id: str) -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await fetch_stored_reports(report_id=report_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")

    row = rows[0]
    report = row.get("report") or {}
    report.setdefault("report_id", str(row.get("id")))
    return {
        "success": True,
        "report_id": str(row.get("id")),
        "analysis_id": str(row.get("analysis_id")),
        "created_at": row.get("created_at"),
        "report": report,
    }


async def list_stored_reports(analysis_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    rows = await fetch_stored_reports(analysis_id=analysis_id)
    return {
        "success": True,
        "analysis_id": analysis_id,
        "count": len(rows),
        "reports": [_report_list_item(row) for row in rows],
    }


async def list_stored_competitors(analysis_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    analyses = await asyncio.to_thread(_fetch_analyses_sync, analysis_id)
    competitors: list[dict[str, Any]] = []

    for row in analyses:
        result = row.get("result") or {}
        company_name = (result.get("company") or {}).get("name")
        for competitor in result.get("competitors") or []:
            competitors.append(
                _competitor_summary(
                    competitor,
                    analysis_id=str(row.get("id")),
                    prompt_id=str(row.get("prompt_id")),
                    created_at=row.get("created_at"),
                    company_name=company_name,
                )
            )

    return {
        "success": True,
        "analysis_id": analysis_id,
        "analysis_count": len(analyses),
        "count": len(competitors),
        "competitors": competitors,
    }


async def list_stored_content(analysis_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    analyses = await asyncio.to_thread(_fetch_analyses_sync, analysis_id)
    content = _flatten_content(analyses)

    return {
        "success": True,
        "analysis_id": analysis_id,
        "analysis_count": len(analyses),
        "count": len(content),
        "content": content,
    }


async def list_stored_hashtags(analysis_id: str | None = None) -> dict[str, Any]:
    _ensure_storage_configured()
    analyses = await asyncio.to_thread(_fetch_analyses_sync, analysis_id)
    hashtag_data = _collect_hashtags(analyses)

    return {
        "success": True,
        "analysis_id": analysis_id,
        "analysis_count": len(analyses),
        **hashtag_data,
    }


def _analysis_overview_item(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result") or {}
    company = result.get("company") or {}
    meta = result.get("meta") or {}
    filters = result.get("filters_applied") or {}
    return {
        "analysis_id": str(row.get("id")),
        "prompt_id": str(row.get("prompt_id")),
        "created_at": row.get("created_at"),
        "company_name": company.get("name"),
        "region": filters.get("region"),
        "competitor_count": int(result.get("competitor_count") or 0),
        "post_count": int(result.get("post_count") or 0),
        "status": meta.get("status"),
        "summary": result.get("summary"),
    }


def _competitor_analytics_item(competitor: dict[str, Any]) -> dict[str, Any]:
    strategy = competitor.get("content_strategy") or {}
    return {
        "username": competitor.get("username"),
        "name": competitor.get("name"),
        "followers": competitor.get("followers"),
        "profile_url": competitor.get("profile_url"),
        "profile_picture_url": competitor.get("profile_picture_url"),
        "match_score": competitor.get("match_score"),
        "post_count": strategy.get("post_count") or competitor.get("post_count") or 0,
        "primary_format": strategy.get("primary_format"),
        "primary_content_category": strategy.get("primary_content_category"),
        "content_focus": strategy.get("content_focus"),
        "avg_engagement_rate": strategy.get("avg_engagement_rate"),
        "media_types": strategy.get("media_types") or [],
        "content_categories": strategy.get("content_categories") or [],
        "top_hashtags": strategy.get("top_hashtags") or [],
    }


def _content_analytics(result: dict[str, Any]) -> dict[str, Any]:
    market = result.get("market_insights") or {}
    media_counts: Counter[str] = Counter()
    for competitor in result.get("competitors") or []:
        for post in competitor.get("posts") or []:
            media_type = post.get("media_type") or "Unknown"
            media_counts[media_type] += 1

    return {
        "total_posts": int(result.get("post_count") or 0),
        "by_media_type": [
            {"type": media_type, "count": count}
            for media_type, count in media_counts.most_common()
        ],
        "dominant_content_types": market.get("dominant_content_types") or [],
        "dominant_content_categories": market.get("dominant_content_categories") or [],
        "content_usage": market.get("content_usage") or {},
        "top_posts": _top_posts(result, limit=5),
    }


def _build_analytics_payload(
    row: dict[str, Any],
    prompt: dict[str, Any] | None,
    *,
    recent_analyses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = row.get("result") or {}
    company = result.get("company") or {}
    filters = result.get("filters_applied") or {}
    market = result.get("market_insights") or {}
    hashtag_data = _collect_hashtags([row])
    analysis_id = str(row.get("id"))

    competitors = [
        _competitor_analytics_item(
            _competitor_summary(
                competitor,
                analysis_id=analysis_id,
                prompt_id=str(row.get("prompt_id")),
                created_at=row.get("created_at"),
                company_name=company.get("name"),
            )
        )
        for competitor in result.get("competitors") or []
    ]

    return {
        "analysis_id": analysis_id,
        "prompt_id": str(row.get("prompt_id")),
        "overview": {
            "company_name": company.get("name") or (prompt or {}).get("company_name"),
            "region": (prompt or {}).get("region") or filters.get("region"),
            "platform": (result.get("meta") or {}).get("platform") or "instagram",
            "matching_mode": result.get("matching_mode"),
            "competitor_count": int(result.get("competitor_count") or len(competitors)),
            "post_count": int(result.get("post_count") or 0),
            "analysis_created_at": row.get("created_at"),
            "summary": result.get("summary"),
            "success": bool(result.get("success")),
        },
        "market_insights": {
            "topics": market.get("topics") or [],
            "dominant_themes": market.get("dominant_themes") or [],
            "content_usage": market.get("content_usage") or {},
        },
        "competitors": competitors,
        "content": _content_analytics(result),
        "hashtags": {
            "total_unique": hashtag_data["total_unique"],
            "top_hashtags": hashtag_data["hashtags"][:15],
        },
        "recent_analyses": recent_analyses or [],
    }


async def get_competitor_analytics(analysis_id: str | None = None) -> dict[str, Any]:
    """Return a dashboard-ready analytics payload from stored analysis data."""
    _ensure_storage_configured()
    analyses = await asyncio.to_thread(_fetch_analyses_sync, analysis_id)

    if not analyses:
        return {
            "success": True,
            "analysis_id": analysis_id,
            "message": "No analysis data found. Run POST /competitor-analysis/analyze first.",
            "overview": None,
            "competitors": [],
            "content": None,
            "hashtags": None,
            "recent_analyses": [],
        }

    recent = [_analysis_overview_item(row) for row in analyses[:10]]
    target = analyses[0]
    prompt = await asyncio.to_thread(_fetch_prompt_sync, str(target.get("prompt_id")))

    return {
        "success": True,
        **_build_analytics_payload(target, prompt, recent_analyses=recent),
    }


async def get_stored_analysis_result(analysis_id: str | None = None) -> dict[str, Any]:
    """Return the exact competitor-agent response JSON saved in the analysis table."""
    _ensure_storage_configured()
    analyses = await asyncio.to_thread(_fetch_analyses_sync, analysis_id)
    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="No analysis data found. Run POST /competitor-analysis/analyze first.",
        )
    return _row_to_agent_result(analyses[0])


async def delete_stored_analysis_result(analysis_id: str) -> dict[str, Any]:
    """Delete a stored competitor analysis result (and related prompt/reports)."""
    _ensure_storage_configured()
    analysis_id = (analysis_id or "").strip()
    if not analysis_id:
        raise HTTPException(status_code=400, detail="analysis_id is required")

    try:
        deleted = await delete_competitor_analysis(analysis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete analysis: {exc}",
        ) from exc

    return {
        "success": True,
        "message": "Competitor analysis result deleted",
        **deleted,
    }


async def list_stored_analysis_results(
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Return full saved agent payloads for recent competitor analysis runs."""
    _ensure_storage_configured()
    limit = max(1, min(int(limit or 20), 100))
    offset = max(0, int(offset or 0))
    analyses = await asyncio.to_thread(_fetch_analyses_sync, None)
    page = analyses[offset : offset + limit]
    results = [_row_to_agent_result(row) for row in page]
    return {
        "success": True,
        "count": len(results),
        "total": len(analyses),
        "limit": limit,
        "offset": offset,
        "results": results,
    }


def _row_to_agent_result(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("result")
    if isinstance(raw, str):
        import json

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"raw_result": raw}
    elif isinstance(raw, dict):
        result = dict(raw)
    else:
        result = {}

    result.setdefault("meta", {})
    if isinstance(result["meta"], dict):
        result["meta"]["analysis_id"] = str(row.get("id"))
        result["meta"]["prompt_id"] = str(row.get("prompt_id")) if row.get("prompt_id") else None
        result["meta"]["created_at"] = row.get("created_at")
        result["meta"]["success"] = row.get("success")
    return result
