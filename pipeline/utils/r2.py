"""Cloudflare R2 client + asset upload helpers.

R2 is S3-compatible; we use boto3 with a custom ``endpoint_url``. One bucket
(``R2_BUCKET_NAME``) holds every asset, namespaced by key prefix:

    extractions/{lead_id}/{logo,hero}.{ext}
    sites/{slug}/...

The Extractor calls :func:`upload_bytes` with already-fetched image bytes.
Idempotency is implicit — ``put_object`` overwrites the same key on rerun,
which is the intended behavior for re-extraction of the same lead.
"""

from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from pipeline.config import get_settings


class R2ConfigError(RuntimeError):
    """R2 settings are missing or incomplete on first use."""


class R2UploadError(RuntimeError):
    """``put_object`` failed after boto3 exhausted its retries."""


_REQUIRED_CREDENTIAL_VARS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
)


def _resolve_endpoint(account_id: str, configured: str) -> str:
    if configured:
        return configured
    if account_id:
        return f"https://{account_id}.r2.cloudflarestorage.com"
    raise R2ConfigError("R2_ENDPOINT is empty and R2_ACCOUNT_ID is empty")


@lru_cache(maxsize=1)
def get_client() -> BaseClient:
    """Lazy boto3 S3 client pointed at R2. Cached per process."""
    settings = get_settings()
    missing = [var for var in _REQUIRED_CREDENTIAL_VARS if not getattr(settings, var)]
    if missing:
        raise R2ConfigError(f"missing required R2 settings: {', '.join(missing)}")

    endpoint = _resolve_endpoint(settings.R2_ACCOUNT_ID, settings.R2_ENDPOINT)

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        # R2 ignores region but boto3 requires one to sign requests.
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def upload_bytes(
    key: str,
    body: bytes,
    content_type: str,
    *,
    cache_control: str | None = None,
) -> str:
    """Upload ``body`` to R2 under ``key``; return ``key`` on success.

    Raises:
        R2ConfigError: R2 settings are not configured.
        R2UploadError: boto3 raised ClientError or BotoCoreError.
    """
    client = get_client()
    bucket = get_settings().R2_BUCKET_NAME

    extra: dict[str, str] = {}
    if cache_control is not None:
        extra["CacheControl"] = cache_control

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            **extra,
        )
    except (ClientError, BotoCoreError) as e:
        raise R2UploadError(f"R2 put_object failed for key {key!r}") from e

    return key


def public_url(key: str) -> str:
    """Compose a public URL for ``key`` from ``R2_PUBLIC_BASE_URL``.

    Raises:
        R2ConfigError: ``R2_PUBLIC_BASE_URL`` is not configured.
    """
    base = get_settings().R2_PUBLIC_BASE_URL
    if not base:
        raise R2ConfigError("R2_PUBLIC_BASE_URL is empty")
    return f"{base.rstrip('/')}/{key.lstrip('/')}"


__all__ = [
    "R2ConfigError",
    "R2UploadError",
    "get_client",
    "public_url",
    "upload_bytes",
]
