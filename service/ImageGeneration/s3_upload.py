from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
from uuid import uuid4

from config.credential_config import config


def s3_configured() -> bool:
    return bool(
        (config.AWS_ACCESS_KEY_ID or "").strip()
        and (config.AWS_SECRET_ACCESS_KEY or "").strip()
        and (config.AWS_S3_BUCKET_NAME or "").strip()
        and (config.AWS_S3_REGION or "").strip()
    )


def _safe_key_part(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._/-]+", "_", (value or "image").strip())
    return text.strip("/_") or "image"


@lru_cache(maxsize=1)
def _s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for S3 uploads. Add boto3 to requirements.txt."
        ) from exc

    return boto3.client(
        "s3",
        region_name=(config.AWS_S3_REGION or "").strip(),
        aws_access_key_id=(config.AWS_ACCESS_KEY_ID or "").strip(),
        aws_secret_access_key=(config.AWS_SECRET_ACCESS_KEY or "").strip(),
    )


def build_s3_object_url(*, bucket: str, region: str, key: str) -> str:
    cdn = (getattr(config, "AWS_S3_CDN_URL", None) or "").strip().rstrip("/")
    if cdn:
        return f"{cdn}/{key.lstrip('/')}"
    # Virtual-hosted–style URL
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key.lstrip('/')}"


def upload_bytes_to_s3(
    data: bytes,
    *,
    filename: str,
    content_type: str = "image/png",
    prefix: str | None = None,
    company_id: str | None = None,
) -> dict[str, Any]:
    if not s3_configured():
        raise RuntimeError(
            "AWS S3 is not configured. Set AWS_ACCESS_KEY_ID, "
            "AWS_SECRET_ACCESS_KEY, AWS_S3_REGION, AWS_S3_BUCKET_NAME."
        )

    bucket = (config.AWS_S3_BUCKET_NAME or "").strip()
    region = (config.AWS_S3_REGION or "").strip()
    folder = (
        prefix
        if prefix is not None
        else (getattr(config, "AWS_S3_PREFIX", None) or "generated-images")
    )
    folder = str(folder).strip().strip("/")
    company = _safe_key_part(str(company_id or "").strip()) if company_id else ""
    if company:
        folder = f"{folder}/{company}" if folder else company
    unique = uuid4().hex[:10]
    key = f"{folder}/{_safe_key_part(filename)}" if folder else _safe_key_part(filename)
    # Avoid collisions when filename repeats across runs.
    if "." in key:
        stem, ext = key.rsplit(".", 1)
        key = f"{stem}_{unique}.{ext}"
    else:
        key = f"{key}_{unique}"

    client = _s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
        CacheControl="public, max-age=31536000",
    )

    url = build_s3_object_url(bucket=bucket, region=region, key=key)
    return {
        "bucket": bucket,
        "region": region,
        "key": key,
        "url": url,
        "s3_url": url,
    }
