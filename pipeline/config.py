"""Typed settings loaded from environment variables.

Every env var listed in `.env.example` should have a corresponding field here.
Pydantic validates at import time, so a missing required var fails loudly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_ENV: Literal["staging", "production", "local"] = "staging"
    APP_BASE_URL: str
    APP_SECRET_KEY: str

    # Database
    DATABASE_URL: str

    # Prefect
    PREFECT_API_URL: str
    PREFECT_API_KEY: str

    # Cloudflare R2
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str = "bettersite-assets"
    R2_ENDPOINT: str
    R2_PUBLIC_BASE_URL: str

    # Anthropic
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_COST_CEILING_PER_BATCH_USD: float = 20.0

    # Data sources
    GOOGLE_MAPS_API_KEY: str
    HUNTER_API_KEY: str
    ZEROBOUNCE_API_KEY: str
    PAGESPEED_API_KEY: str = ""

    # Stripe
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_ID: str

    # Sentry
    SENTRY_DSN: str = ""

    # Admin auth
    ADMIN_BASIC_AUTH_USER: str
    ADMIN_BASIC_AUTH_PASSWORD: str

    # Strategy selectors
    EXTRACTION_STRATEGY: Literal["html_only", "vision_full", "hybrid", "gmb_first"] = "html_only"
    SALES_AGENT_BACKEND: Literal[
        "null", "console", "smartlead", "instantly", "smtp", "postmark"
    ] = "null"

    # Tuning knobs
    SCANNER_PASS_THRESHOLD: int = Field(default=60, ge=0, le=100)
    PREVIEW_EXPIRY_HOURS: int = Field(default=48, ge=1)
    FOLLOWUP_DELAY_HOURS: int = Field(default=24, ge=1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Import this, not the class directly."""
    return Settings()  # type: ignore[call-arg]
