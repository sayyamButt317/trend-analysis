import re

SOURCE_WEIGHTS = {
    "Instagram Creators":1.0,
    "Instagram Blog":0.95,
    "Google Trends":0.95,
    "Metricool":0.85,
    "Sprout":0.85,
    "Hootsuite":0.8,
    "Later":0.75,
    "Wikipedia":0.2,
}

STOP_HASHTAGS = {
    "viral",
    "reels",
    "explore",
    "explorepage",
    "instagram",
    "instagood",
    "love",
    "follow",
    "trending",
    "fyp",
}

# Official Google Trends RSS (daily trending searches)
GOOGLE_TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo={geo}"

GOOGLE_TRENDS_GEOS: list[dict[str, str]] = [
    {"geo": "US", "label": "United States", "priority": "high"},
    {"geo": "AE", "label": "United Arab Emirates", "priority": "high"},
    {"geo": "SA", "label": "Saudi Arabia", "priority": "high"},
    {"geo": "GB", "label": "United Kingdom", "priority": "high"},
    {"geo": "PK", "label": "Pakistan", "priority": "high"},
    {"geo": "IN", "label": "India", "priority": "medium"},
    {"geo": "CA", "label": "Canada", "priority": "medium"},
    {"geo": "AU", "label": "Australia", "priority": "medium"},
]

# Map user region strings to Google Trends geo codes
REGION_TO_GEO: dict[str, str] = {
    "gcc": "AE",
    "uae": "AE",
    "united arab emirates": "AE",
    "dubai": "AE",
    "abu dhabi": "AE",
    "saudi": "SA",
    "saudi arabia": "SA",
    "ksa": "SA",
    "riyadh": "SA",
    "jeddah": "SA",
    "mena": "AE",
    "middle east": "AE",
    "usa": "US",
    "us": "US",
    "united states": "US",
    "north america": "US",
    "uk": "GB",
    "united kingdom": "GB",
    "europe": "GB",
    "pakistan": "PK",
    "lahore": "PK",
    "karachi": "PK",
    "india": "IN",
    "canada": "CA",
    "australia": "AU",
    "global": "US",
}

GOOGLE_TREND_QUERY_TEMPLATES = [
    "Google Trends {topic}",
    "Google Trends {country}",
    "Google Trends rising searches {country}",
    "Google Trends trending topics {country}",
    "Google Trends {niche}",
    "Google Trends Instagram {country}",
]

# HTML sources only — Google Trends is fetched via RSS in google_trend_fetcher.py
TREND_SOURCES: list[dict[str, str]] = [
    {
        "url": "https://creators.instagram.com/",
        "name": "Instagram Creators",
        "focus": "algorithm,reels,best_practices,features",
        "priority": "high",
    },
    {
        "url": "https://about.instagram.com/blog",
        "name": "Instagram Blog",
        "focus": "features,updates,algorithm",
        "priority": "high",
    },
    {
        "url": "https://socialbee.com/blog/instagram-trends/",
        "name": "SocialBee",
        "focus": "reel_formats,topics,culture",
        "priority": "high",
    },
    {
        "url": "https://metricool.com/trending-instagram-songs/",
        "name": "Metricool",
        "focus": "songs,audio,reels",
        "priority": "high",
    },
    {
        "url": "https://sproutsocial.com/insights/instagram-reel-hashtags/",
        "name": "Sprout Social",
        "focus": "hashtags,reels",
        "priority": "high",
    },
    {
        "url": "https://blog.hootsuite.com/instagram-algorithm/",
        "name": "Hootsuite",
        "focus": "algorithm,reels",
        "priority": "high",
    },
    {
        "url": "https://later.com/blog/instagram-trends/",
        "name": "Later",
        "focus": "creator_trends,reels",
        "priority": "high",
    },
    {
        "url": "https://blog.buffer.com/",
        "name": "Buffer",
        "focus": "content_strategy,engagement",
        "priority": "medium",
    },
    {
        "url": "https://www.socialinsider.io/blog/",
        "name": "Socialinsider",
        "focus": "analytics,benchmarks",
        "priority": "high",
    },
    {
        "url": "https://awario.com/blog/instagram-hashtags/",
        "name": "Awario",
        "focus": "hashtags,niche",
        "priority": "medium",
    },
    {
        "url": "https://en.wikipedia.org/wiki/2026_is_the_new_2016",
        "name": "Wikipedia",
        "focus": "culture,topics",
        "priority": "low",
    },
]

TREND_QUERY_TEMPLATES = [
    "{platform} {niche} trends {timeframe}",
    "{platform} {niche} trending topics {timeframe}",
    "{platform} {niche} viral posts {timeframe}",
    "{platform} {niche} trending hashtags {timeframe}",
    "{platform} {niche} trending reels {timeframe}",
    "{platform} {niche} trending audio {timeframe}",
    "{platform} {niche} algorithm update",
    "{platform} {niche} creator trends",
    "{platform} {niche} trending formats",
    "{platform} {niche} trending challenges",
    "{platform} {niche} viral creators",
    "{platform} {niche} rising topics",
    "{platform} {niche} trending memes",
]

REGIONAL_QUERY_TEMPLATES = [
    "{platform} {niche} trends in {country}",
    "{platform} {niche} trending hashtags {country}",
    "{platform} {niche} viral creators {country}",
    "{platform} {niche} trending reels {country}",
    "{platform} {niche} trending topics {country}",
]

TAVILY_TREND_QUERIES = [
    "Instagram trends this week",
    "Instagram trending topics today",
    "Instagram viral reels today",
    "Instagram trending reel formats",
    "Instagram trending hashtags today",
    "Instagram trending songs today",
    "Instagram algorithm update 2026",
    "Instagram trends UAE",
    "Instagram trends Saudi Arabia",
    "Instagram trends USA",
    "Google Trends Instagram this week",
    "Google Trends rising searches today",
    "Google Trends UAE trending searches",
    "Google Trends Saudi Arabia trending searches",
]


def resolve_geos_for_region(region: str | None) -> list[str]:
    """Return Google Trends geo codes for a user region (defaults to global set)."""
    if not region:
        return [item["geo"] for item in GOOGLE_TRENDS_GEOS if item.get("priority") == "high"]

    normalized = region.strip().lower()
    for part in re_split_region(normalized):
        if part in REGION_TO_GEO:
            return [REGION_TO_GEO[part]]

    # Multi-region strings like "United States, GCC, MENA, Pakistan"
    geos: list[str] = []
    for part in re_split_region(normalized):
        geo = REGION_TO_GEO.get(part)
        if geo and geo not in geos:
            geos.append(geo)
    return geos or ["US", "AE", "SA"]


def re_split_region(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,/|&]+", text) if part.strip()]
