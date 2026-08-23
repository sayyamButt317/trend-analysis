from collections import Counter
from typing import Any
from agents.trend.services.content_analyzer import build_market_content_usage
from service.Competitor.competitor_analysis_sections import build_analysis_sections
from service.Competitor.competitive_comparison import (
    build_competitor_vs_company_comparison,
    build_quantified_competitive_gaps,
)
from service.Competitor.competitor_intelligence_report import (
    _competitor_lookup_key,
    similarity_to_percentages,
)


def _similarity_lookup(similarity_scores: list[dict] | None) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in similarity_scores or []:
        key = _competitor_lookup_key(item)
        if key:
            lookup[key] = item
    return lookup


def _attach_similarity_fields(
    profile: dict[str, Any],
    *,
    source: dict[str, Any],
    score_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    matched = score_lookup.get(_competitor_lookup_key(source))
    similarity = (
        (matched or {}).get("similarity")
        or source.get("similarity")
        or {}
    )
    if similarity:
        profile["similarity"] = similarity
        profile["similarity_percentages"] = (
            (matched or {}).get("similarity_percentages")
            or source.get("similarity_percentages")
            or similarity_to_percentages(similarity)
        )
        profile["match_score"] = (
            (matched or {}).get("match_score")
            or source.get("match_score")
            or similarity.get("overall")
        )
    return profile


def _normalize_media_type(post: dict) -> str:
    media_type = (post.get("media_type") or "").upper()
    product_type = (post.get("media_product_type") or "").upper()
    if product_type == "REELS" or media_type in {"REEL", "VIDEO"}:
        return "Reels"
    if media_type == "CAROUSEL_ALBUM":
        return "Carousel"
    if media_type == "IMAGE":
        return "Image"
    return media_type.title() if media_type else "Unknown"


def _simplify_post(post: dict) -> dict:
    return {
        "id": post.get("id") or post.get("media_id"),
        "caption": post.get("caption") or "",
        "media_type": _normalize_media_type(post),
        "media_url": post.get("media_url"),
        "thumbnail_url": post.get("thumbnail_url"),
        "permalink": post.get("permalink"),
        "timestamp": post.get("timestamp"),
        "likes": int(post.get("likes") or post.get("like_count") or 0),
        "comments": int(post.get("comments") or post.get("comments_count") or 0),
        "engagement_rate": float(post.get("engagement_rate") or 0),
        "hashtags": post.get("hashtags") or [],
    }


def _simplify_company_social_analysis(analysis: dict[str, Any] | None) -> dict[str, Any]:
    if not analysis:
        return {}
    handles = analysis.get("social_handles") or {}
    instagram = analysis.get("instagram") or (analysis.get("user_instagram") or {}).get("instagram") or {}
    user_ig = analysis.get("user_instagram") or {}
    user_li = analysis.get("user_linkedin") or {}
    company_dna = analysis.get("company_dna") or {}
    return {
        "company_dna": company_dna,
        "user_instagram": {
            "skipped": user_ig.get("skipped"),
            "username": user_ig.get("username") or handles.get("instagram_username"),
            "detected_niche": instagram.get("detected_niche") or analysis.get("detected_niche"),
            "analysis": instagram,
            "post_count": len(user_ig.get("posts") or analysis.get("instagram_posts") or []),
            "warnings": user_ig.get("warnings") or [],
        },
        "user_linkedin": {
            "skipped": user_li.get("skipped"),
            "linkedin_url": user_li.get("linkedin_url") or analysis.get("linkedin_url"),
            "analysis": user_li.get("linkedin_analysis") or analysis.get("linkedin_analysis"),
            "content_themes": user_li.get("linkedin_content_themes") or analysis.get("linkedin_content_themes") or [],
            "post_count": len(user_li.get("linkedin_posts") or analysis.get("linkedin_posts") or []),
            "employees": user_li.get("employees") or analysis.get("employees") or [],
            "employee_count": len(user_li.get("employees") or analysis.get("employees") or []),
            "company_size": user_li.get("company_size") or analysis.get("company_size"),
            "job_openings": user_li.get("job_openings") or analysis.get("job_openings") or [],
            "job_count": len(user_li.get("job_openings") or analysis.get("job_openings") or []),
            "is_hiring": user_li.get("is_hiring") or analysis.get("is_hiring"),
            "hiring_signals": user_li.get("hiring_signals") or analysis.get("hiring_signals") or [],
            "warnings": user_li.get("warnings") or [],
        },
        "social_handles": handles,
        "detected_niche": analysis.get("detected_niche") or instagram.get("detected_niche"),
        "audience_pain_points": (analysis.get("audience_pain_points") or analysis.get("pain_points") or [])[:8],
    }


def build_competitor_response(
    *,
    company: dict[str, Any],
    filters: dict[str, Any],
    competitors: list[dict],
    processed_posts: list[dict],
    content_mix: list[dict],
    topics: list[dict],
    hashtags: list[dict],
    summary: str,
    meta: dict[str, Any],
    error: str | None = None,
    company_profile: dict[str, Any] | None = None,
    search_intelligence: dict[str, Any] | None = None,
    gap_analysis: dict[str, Any] | None = None,
    competitive_gaps: dict[str, Any] | None = None,
    content_intelligence: dict[str, Any] | None = None,
    competitor_intelligence_report: dict[str, Any] | None = None,
    recommendations: list[dict] | None = None,
    ai_report: dict[str, Any] | None = None,
    similarity_scores: list[dict] | None = None,
    company_analysis: dict[str, Any] | None = None,
    competitor_website_intel: list[dict] | None = None,
    web_crawl: dict[str, Any] | None = None,
) -> dict[str, Any]:
    posts_by_username: dict[str, list[dict]] = {}
    for post in processed_posts:
        username = post.get("username")
        if username:
            posts_by_username.setdefault(username, []).append(_simplify_post(post))

    score_lookup = _similarity_lookup(similarity_scores)

    competitor_profiles = []
    for item in content_mix:
        username = item.get("username")
        source = next(
            (comp for comp in competitors if comp.get("username") == username),
            {},
        )
        profile = {
            "username": username,
            "name": source.get("name"),
            "followers": source.get("followers"),
            "profile_url": source.get("profile_url")
            or f"https://www.instagram.com/{username}/",
            "profile_picture_url": source.get("profile_picture_url"),
            "image_url": source.get("profile_picture_url"),
            "bio": source.get("bio"),
            "website": source.get("website"),
            "linkedin_url": source.get("linkedin_url"),
            "linkedin_username": source.get("linkedin_username"),
            "region_match": source.get("region_match"),
            "niche_match": source.get("niche_match"),
            "authenticity": source.get("authenticity"),
            "discovered_by": source.get("discovered_by"),
            "match_reasons": source.get("match_reasons") or [],
            "instagram_analysis": source.get("instagram_analysis"),
            "linkedin_analysis": source.get("linkedin_analysis"),
            "employees": source.get("employees") or [],
            "employee_count": source.get("employee_count")
            or len(source.get("employees") or []),
            "job_openings": source.get("job_openings") or [],
            "company_size": source.get("company_size"),
            "is_hiring": source.get("is_hiring"),
            "hiring_signals": source.get("hiring_signals") or [],
            "social_warnings": source.get("social_warnings") or [],
            "content_strategy": {
                "post_count": item.get("post_count", 0),
                "primary_format": item.get("primary_format"),
                "primary_content_category": item.get("primary_content_category"),
                "content_focus": item.get("content_focus"),
                "media_types": item.get("media_types") or [],
                "content_categories": item.get("content_categories") or [],
                "themes": item.get("content_themes") or [],
                "top_hashtags": item.get("top_hashtags") or [],
                "avg_engagement_rate": item.get("avg_engagement_rate", 0),
                "caption_style": item.get("caption_style") or {},
                "best_performing_format": item.get("best_performing_format"),
            },
            "posts": posts_by_username.get(username, []),
        }
        competitor_profiles.append(_attach_similarity_fields(profile, source=source, score_lookup=score_lookup))

    for comp in competitors:
        username = (comp.get("username") or "").strip().lstrip("@").lower() or None
        already = False
        if username:
            already = any(item.get("username") == username for item in competitor_profiles)
        else:
            already = any(
                (item.get("name") or "").strip().lower() == (comp.get("name") or "").strip().lower()
                for item in competitor_profiles
                if item.get("name")
            )
        if already:
            continue
        profile = {
            "username": username,
            "name": comp.get("name"),
            "followers": comp.get("followers"),
            "profile_url": comp.get("profile_url"),
            "profile_picture_url": comp.get("profile_picture_url"),
            "image_url": comp.get("profile_picture_url"),
            "bio": comp.get("bio"),
            "website": comp.get("website"),
            "linkedin_url": comp.get("linkedin_url"),
            "linkedin_username": comp.get("linkedin_username"),
            "region_match": comp.get("region_match"),
            "niche_match": comp.get("niche_match"),
            "authenticity": comp.get("authenticity"),
            "discovered_by": comp.get("discovered_by"),
            "match_reasons": comp.get("match_reasons") or [],
            "instagram_analysis": comp.get("instagram_analysis"),
            "linkedin_analysis": comp.get("linkedin_analysis"),
            "employees": comp.get("employees") or [],
            "employee_count": comp.get("employee_count") or len(comp.get("employees") or []),
            "job_openings": comp.get("job_openings") or [],
            "company_size": comp.get("company_size"),
            "is_hiring": comp.get("is_hiring"),
            "hiring_signals": comp.get("hiring_signals") or [],
            "social_warnings": comp.get("social_warnings") or [],
            "content_strategy": {
                "post_count": 0,
                "primary_format": None,
                "primary_content_category": None,
                "content_focus": None,
                "media_types": [],
                "content_categories": [],
                "themes": [],
                "top_hashtags": [],
                "avg_engagement_rate": 0,
                "caption_style": {},
                "best_performing_format": None,
            },
            "posts": posts_by_username.get(username, []) if username else [],
        }
        competitor_profiles.append(_attach_similarity_fields(profile, source=comp, score_lookup=score_lookup))

    all_media = Counter(
        media["type"]
        for profile in competitor_profiles
        for media in profile["content_strategy"]["media_types"]
        for _ in range(media.get("count", 0))
    )
    all_themes = Counter(
        theme["theme"]
        for profile in competitor_profiles
        for theme in profile["content_strategy"]["themes"]
        for _ in range(theme.get("count", 0))
    )
    all_hashtags = Counter(
        tag for profile in competitor_profiles for tag in profile["content_strategy"]["top_hashtags"]
    )
    all_categories = Counter(
        category["category"]
        for profile in competitor_profiles
        for category in profile["content_strategy"]["content_categories"]
        for _ in range(category.get("count", 0))
    )

    post_count = len(processed_posts)
    competitor_count = len(competitor_profiles)
    if error and competitor_count == 0:
        success = False
    elif competitor_count > 0 or post_count > 0:
        success = True
    else:
        success = not error
    content_usage = build_market_content_usage(content_mix, processed_posts)

    market_insights = {
        "topics": topics[:10],
        "content_usage": content_usage,
        "dominant_content_types": [
            {"type": media_type, "count": count}
            for media_type, count in all_media.most_common(5)
        ],
        "dominant_content_categories": [
            {"category": category, "count": count}
            for category, count in all_categories.most_common(5)
        ],
        "dominant_themes": [
            {"theme": theme, "count": count}
            for theme, count in all_themes.most_common(5)
        ],
        "top_hashtags": [
            {"tag": tag, "count": count} for tag, count in all_hashtags.most_common(10)
        ],
        "hashtag_summary": hashtags[:10],
    }

    analysis = build_analysis_sections(
        company=company,
        company_profile=company_profile,
        company_analysis=company_analysis,
        competitor_intelligence_report=competitor_intelligence_report,
        gap_analysis=gap_analysis,
        search_intelligence=search_intelligence,
        web_crawl=web_crawl,
        similarity_scores=similarity_scores,
        recommendations=recommendations,
        competitor_website_intel=competitor_website_intel,
        content_mix=content_mix,
        market_insights=market_insights,
        competitors=competitor_profiles,
        processed_posts=processed_posts,
    )

    competitor_vs_company = build_competitor_vs_company_comparison(
        company=company,
        company_profile=company_profile,
        company_analysis=company_analysis,
        competitors=competitor_profiles,
        competitor_intelligence_report=competitor_intelligence_report,
    )
    quantified_gaps = build_quantified_competitive_gaps(
        gap_analysis=gap_analysis,
        competitor_intelligence_report=competitor_intelligence_report,
        competitor_count=len(competitor_profiles),
    )
    analysis["competitor_vs_company_comparison"] = competitor_vs_company
    analysis["quantified_competitive_gaps"] = quantified_gaps
    analysis["competitive_gaps"] = competitive_gaps or {}
    analysis["content_intelligence"] = content_intelligence or {}

    return {
        "success": success,
        "error": error,
        "summary": summary,
        "company": {
            "name": company.get("name"),
            "instagram_username": company.get("instagram_username"),
            "instagram_url": company.get("instagram_url"),
            "linkedin_url": company.get("linkedin_url"),
            "website": company.get("website"),
            "services": company.get("services") or [],
            "flagship_services": company.get("flagship_services") or [],
            "extracted_signals": company.get("company_signals") or filters.get("company_signals") or {},
        },
        "company_social_analysis": _simplify_company_social_analysis(company_analysis),
        "filters_applied": filters,
        "matching_mode": filters.get("matching_mode") or "smart",
        "discovery_warnings": filters.get("discovery_warnings") or [],
        "competitor_intelligence": filters.get("competitor_intelligence"),
        "competitor_count": len(competitors),
        "post_count": post_count,
        "competitors": competitor_profiles,
        "analysis": analysis,
        "strategic_insights": analysis.get("strategic_insights") or {},
        "customer_insights": (analysis.get("strategic_insights") or {}).get("customer_insights") or {},
        "market_insights": market_insights,
        "meta": meta,
        "company_profile": company_profile or {},
        "search_intelligence": search_intelligence or {},
        "gap_analysis": gap_analysis or {},
        "competitive_gaps": competitive_gaps or {},
        "content_intelligence": content_intelligence or {},
        "competitor_vs_company_comparison": competitor_vs_company,
        "quantified_competitive_gaps": quantified_gaps,
        "company_analysis": company_analysis,
        "competitor_intelligence_report": competitor_intelligence_report,
        "recommendations": recommendations or [],
        "ai_report": ai_report or {},
        "similarity_scores": similarity_scores or [],
        "competitor_website_intel": competitor_website_intel or [],
        "web_crawl": web_crawl or {},
    }
