import asyncio
import logging
import time
import httpx
from config.credential_config import config
from core.api_call_counter import record_api_call

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 20.0
DEFAULT_READ_TIMEOUT = 90.0
DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (2.0, 5.0, 10.0)


class InstagramRateLimitError(RuntimeError):
    pass


class InstagramApiError(RuntimeError):
    pass


def _api_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=DEFAULT_CONNECT_TIMEOUT,
        read=DEFAULT_READ_TIMEOUT,
        write=30.0,
        pool=DEFAULT_CONNECT_TIMEOUT,
    )


def _validate_api_config() -> None:
    if not (config.INSTAGRAM_USER_ID or "").strip():
        raise InstagramApiError("IG_USER_ID is not configured")
    if not (config.INSTAGRAM_PAGE_ACCESS_TOKEN or "").strip():
        raise InstagramApiError("INSTAPAGE_ACCESS_TOKEN is not configured")


async def ExtractInfluencerDetailsFromInstagram(username: str, *, post_limit: int = 25) -> dict | None:
    post_limit = max(1, min(int(post_limit), 25))
    _validate_api_config()

    handle = (username or "").strip().lstrip("@")
    url = f"https://graph.facebook.com/v23.0/{config.INSTAGRAM_USER_ID}"
    params = {
        "fields": f"""
        business_discovery.username({handle}){{
            id,
            username,
            name,
            biography,
            website,
            followers_count,
            follows_count,
            media_count,
            profile_picture_url,
            media.limit({post_limit}){{
                id,
                caption,
                media_type,
                media_product_type,
                media_url,
                permalink,
                thumbnail_url,
                timestamp,
                like_count,
                comments_count
            }}
        }}
        """,
        "access_token": config.INSTAGRAM_PAGE_ACCESS_TOKEN,
    }

    last_error: Exception | None = None
    for attempt in range(DEFAULT_MAX_RETRIES):
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=_api_timeout()) as client:
                record_api_call("instagram")
                response = await client.get(url, params=params)

            if response.status_code != 200:
                error = response.json().get("error", {}) if response.content else {}
                code = error.get("code")
                message = error.get("message") or response.text
                if response.status_code == 429 or code in {4, 17, 32, 613}:
                    raise InstagramRateLimitError(message or "Instagram API rate limit reached")
                if response.status_code in {500, 502, 503, 504} and attempt < DEFAULT_MAX_RETRIES - 1:
                    last_error = InstagramApiError(message)
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    continue
                logger.warning(
                    "Instagram API error for @%s status=%s message=%s",
                    handle,
                    response.status_code,
                    message,
                )
                return None

            data = response.json()
            profile = data.get("business_discovery") or {}
            media_count = len((profile.get("media") or {}).get("data") or [])
            logger.info(
                "Fetched @%s in %.1fs (%s posts)",
                handle,
                time.time() - start_time,
                media_count,
            )
            return profile

        except InstagramRateLimitError:
            raise
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
            last_error = exc
            logger.warning(
                "Instagram API timeout for @%s (attempt %s/%s): %s",
                handle,
                attempt + 1,
                DEFAULT_MAX_RETRIES,
                type(exc).__name__,
            )
            if attempt < DEFAULT_MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])
        except httpx.RequestError as exc:
            last_error = exc
            logger.warning(
                "Instagram API network error for @%s (attempt %s/%s): %s",
                handle,
                attempt + 1,
                DEFAULT_MAX_RETRIES,
                exc,
            )
            if attempt < DEFAULT_MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])

    logger.error(
        "Instagram API failed for @%s after %s attempts: %s",
        handle,
        DEFAULT_MAX_RETRIES,
        last_error,
    )
    return None
