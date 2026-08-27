import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Config(BaseModel):
    OPENAI_API_KEY: str = Field(default=os.getenv("OPENAI_API_KEY"))
    OPENAI_MODEL_NAME: str = Field(
        default=os.getenv("OPENAI_MODEL_NAME") or "gpt-4o",
        description="Use gpt-4o or gpt-4o-mini. Invalid values like gpt-5.5 fall back to gpt-4o.",
    )

    INSTAGRAM_APP_ID: str = Field(default=os.getenv("INSTAGRAM_APP_ID"))
    INSTAGRAM_APP_SECRET: str = Field(default=os.getenv("INSTAGRAM_APP_SECRET"))
    INSTAGRAM_REDIRECT_URL: str = Field(default=os.getenv("INSTAGRAM_REDIRECT_URL"))
    INSTAGRAM_ACCESS_TOKEN: str = Field(default=os.getenv("INSTAGRAM_ACCESS_TOKEN"))
    INSTAGRAMPAGE_ACCESS_TOKEN: str = Field(default=os.getenv("INSTAPAGE_ACCESS_TOKEN"))
    INSTAGRAM_USER_ID: str = Field(default=os.getenv("IG_USER_ID"))
    INSTAGRAM_SESSIONID: str = Field(default=os.getenv("INSTAGRAM_SESSIONID"))

    META_VERIFY_TOKEN: str = Field(default=os.getenv("META_VERIFY_TOKEN"))
    META_APP_SECRET: str = Field(default=os.getenv("META_APP_SECRET"))
    PAGE_ACCESS_TOKEN: str = Field(default=os.getenv("PAGE_ACCESS_TOKEN"))
    IG_GRAPH_API_VERSION: str = Field(default=os.getenv("IG_GRAPH_API_VERSION"))
    IG_BUSINESS_ID: str = Field(default=os.getenv("IG_BUSINESS_ID"))
    INSTAGRAM_PAGE_ACCESS_TOKEN: str = Field(
        default=os.getenv("INSTAPAGE_ACCESS_TOKEN")
    )

    REDIS_URL: str = Field(default=os.getenv("REDIS_URL"))
    INSTAGRAM_AGENT_RUN_INTERVAL_HOURS: int = Field(
        default=int(os.getenv("INSTAGRAM_AGENT_RUN_INTERVAL_HOURS", "1"))
    )
    INSTAGRAM_PROFILE_RESYNC_DAYS: int = Field(
        default=int(os.getenv("INSTAGRAM_PROFILE_RESYNC_DAYS", "7"))
    )
    INSTAGRAM_AGENT_BATCH_SIZE: int = Field(
        default=int(os.getenv("INSTAGRAM_AGENT_BATCH_SIZE", "100"))
    )
    INSTAGRAM_SYNC_REQUEST_DELAY_SECONDS: int = Field(
        default=int(os.getenv("INSTAGRAM_SYNC_REQUEST_DELAY_SECONDS", "3"))
    )
    INSTAGRAM_RATE_LIMIT_COOLDOWN_SECONDS: int = Field(
        default=int(os.getenv("INSTAGRAM_RATE_LIMIT_COOLDOWN_SECONDS", "3600"))
    )
    INSTAGRAM_RATE_LIMIT_RETRY_COUNTDOWN: int = Field(
        default=int(os.getenv("INSTAGRAM_RATE_LIMIT_RETRY_COUNTDOWN", "900"))
    )
    INSTAGRAM_RATE_LIMIT_MAX_RETRIES: int = Field(
        default=int(os.getenv("INSTAGRAM_RATE_LIMIT_MAX_RETRIES", "5"))
    )
    LOGO_DEV_PUBLIC_KEY: str = Field(default=os.getenv("LOGO_DEV_PUBLIC_KEY"))
    LOGO_DEV_SECRET_KEY: str = Field(default=os.getenv("LOGO_DEV_SECRET_KEY"))
    TRAVILY_API_KEY: str = Field(
        default=os.getenv("TRAVILY_API_KEY") or os.getenv("TAVILY_API_KEY")
    )

    SUPABASE_URL: str = Field(default=os.getenv("SUPABASE_URL"))
    SUPABASE_KEY: str = Field(default=os.getenv("SUPABASE_KEY"))
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default=os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    SUPABASE_ANON_KEY: str = Field(default=os.getenv("SUPABASE_ANON_KEY"))
    SUPABASE_TABLE_PROMPTS: str = Field(
        default=os.getenv("SUPABASE_TABLE_PROMPTS") or "prompts"
    )
    SUPABASE_TABLE_ANALYSIS: str = Field(
        default=os.getenv("SUPABASE_TABLE_ANALYSIS") or "analysis"
    )
    SUPABASE_TABLE_REPORTS: str = Field(
        default=os.getenv("SUPABASE_TABLE_REPORTS") or "reports"
    )
    SUPABASE_TABLE_TRENDS: str = Field(
        default=os.getenv("SUPABASE_TABLE_TRENDS") or "trends"
    )
    SUPABASE_TABLE_COMPETITORSANALYSIS: str = Field(
        default=os.getenv("SUPABASE_TABLE_COMPETITORSANALYSIS") or "competitorsanalysis"
    )
    SUPABASE_TABLE_CONTENT_RECOMMENDATION: str = Field(
        default=os.getenv("SUPABASE_TABLE_CONTENT_RECOMMENDATION") or "content_recommendation"
    )
    SUPABASE_TABLE_SCRIPT: str = Field(
        default=os.getenv("SUPABASE_TABLE_SCRIPT") or "script"
    )
    SUPABASE_TABLE_IMAGES: str = Field(
        default=os.getenv("SUPABASE_TABLE_IMAGES") or "images"
    )
    FIRECRAWL_API_KEY: str = Field(default=os.getenv("FIRECRAWL_API_KEY"))

    HIGGSFIELD_API_KEY: str = Field(
        default=os.getenv("HIGGSFIELD_API_KEY") or os.getenv("HF_KEY") or ""
    )
    HIGGSFIELD_API_KEY_ID: str = Field(
        default=os.getenv("HIGGSFIELD_API_KEY_ID")
        or os.getenv("HIGGSFEED_API_KEY_ID")
        or os.getenv("HF_API_KEY")
        or ""
    )
    HIGGSFIELD_API_KEY_SECRET: str = Field(
        default=os.getenv("HIGGSFIELD_API_KEY_SECRET")
        or os.getenv("HIGGSFEED_API_KEY_SECRET")
        or os.getenv("HF_API_SECRET")
        or ""
    )
    HIGGSFIELD_IMAGE_MODEL: str = Field(
        default=os.getenv("HIGGSFIELD_IMAGE_MODEL") or "higgsfield-ai/soul/standard"
    )
    HIGGSFIELD_VIDEO_MODEL: str = Field(
        default=os.getenv("HIGGSFIELD_VIDEO_MODEL") or "higgsfield-ai/dop/standard"
    )
    HIGGSFIELD_MCP_URL: str = Field(
        default=os.getenv("HIGGSFIELD_MCP_URL") or "https://mcp.higgsfield.ai/mcp"
    )
    GEMINI_API_KEY: str = Field(default=os.getenv("GEMINI_API_KEY"))
    GEMINI_MODEL_NAME: str = Field(default=os.getenv("GEMINI_MODEL_NAME"))
    GEMINI_IMAGE_MODEL: str = Field(
        default=os.getenv("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image",
        description="Gemini model used for still image generation.",
    )
    GEMINI_IMAGE_MODEL_FALLBACKS: str = Field(
        default=os.getenv("GEMINI_IMAGE_MODEL_FALLBACKS")
        or "gemini-2.0-flash-preview-image-generation",
        description="Comma-separated fallback Gemini image models when the primary is unavailable.",
    )
    GEMINI_IMAGE_MAX_RETRIES: int = Field(
        default=int(os.getenv("GEMINI_IMAGE_MAX_RETRIES", "3")),
        description="Retry count per model for transient Gemini errors (503/429/5xx).",
    )
    AWS_ACCESS_KEY_ID: str = Field(default=os.getenv("AWS_ACCESS_KEY_ID"))
    AWS_SECRET_ACCESS_KEY: str = Field(default=os.getenv("AWS_SECRET_ACCESS_KEY"))
    AWS_REGION: str = Field(
        default=os.getenv("AWS_REGION") or os.getenv("AWS_S3_REGION") or "",
        description="AWS region for S3 (preferred). Also accepts AWS_S3_REGION.",
    )
    AWS_S3_REGION: str = Field(
        default=os.getenv("AWS_S3_REGION") or os.getenv("AWS_REGION") or "",
        description="Deprecated alias for AWS_REGION (kept for back-compat).",
    )
    AWS_S3_BUCKET_NAME: str = Field(default=os.getenv("AWS_S3_BUCKET_NAME"))
    AWS_S3_PREFIX: str = Field(
        default=os.getenv("AWS_S3_PREFIX") or "generated-images",
        description="Folder/prefix inside the S3 bucket for generated assets.",
    )
    

config = Config()


def higgsfield_api_key() -> str:
    combined = (config.HIGGSFIELD_API_KEY or "").strip()
    if combined:
        return combined
    key_id = (config.HIGGSFIELD_API_KEY_ID or "").strip()
    secret = (config.HIGGSFIELD_API_KEY_SECRET or "").strip()
    if key_id and secret:
        return f"{key_id}:{secret}"
    return ""


def resolve_supabase_api_key() -> str: 
    for candidate in (
        config.SUPABASE_SERVICE_ROLE_KEY,
        config.SUPABASE_KEY,
        config.SUPABASE_ANON_KEY,
    ):
        key = (candidate or "").strip()
        if not key:
            continue
        if key.startswith("sb_publishable_"):
            continue
        return key
    return ""
