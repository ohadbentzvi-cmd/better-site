"""Typed settings loaded from environment variables.

Phase-gated: only fields the current codepath actually uses are required.
Everything else is optional with an empty default. When a feature lands that
needs a given var, either promote it to required here or have the feature
validate it at call time.

Required today (Phase 1 worker):
    DATABASE_URL   — app DB (ops.* / app.*)
    PREFECT_API_URL — Prefect server REST API
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Required (Phase 1) ───────────────────────────────────────────────────
    DATABASE_URL: str
    PREFECT_API_URL: str

    # ── Optional (auth not configured on self-hosted Prefect server) ─────────
    PREFECT_API_KEY: str = ""

    # ── Optional until their feature ships ───────────────────────────────────
    APP_ENV: Literal["staging", "production", "local"] = "staging"
    APP_BASE_URL: str = ""
    APP_SECRET_KEY: str = ""

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "bettersite-assets"
    R2_ENDPOINT: str = ""
    R2_PUBLIC_BASE_URL: str = ""

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_COST_CEILING_PER_BATCH_USD: float = 20.0

    GOOGLE_MAPS_API_KEY: str = ""
    HUNTER_API_KEY: str = ""
    ZEROBOUNCE_API_KEY: str = ""
    PAGESPEED_API_KEY: str = ""

    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""

    SENTRY_DSN: str = ""

    ADMIN_BASIC_AUTH_USER: str = ""
    ADMIN_BASIC_AUTH_PASSWORD: str = ""

    # Admin Review Console (Phase 5, pulled forward).
    #   ADMIN_SERVICE_TOKEN — shared secret between Next.js web and FastAPI;
    #       FastAPI rejects any /admin/* request without a matching token.
    #       Must be >=32 bytes of random in production.
    #   ADMIN_SESSION_SECRET — HMAC key Next.js uses to sign its session cookie.
    #       Read by web/ only; listed here so it's documented in one place.
    ADMIN_SERVICE_TOKEN: str = ""
    ADMIN_SESSION_SECRET: str = ""
    ADMIN_LOGIN_RATE_LIMIT_WINDOW_MIN: int = Field(default=15, ge=1, le=1440)
    ADMIN_LOGIN_RATE_LIMIT_MAX_FAILURES: int = Field(default=5, ge=1, le=100)

    # One-time superadmin seed. Consumed by the migration that adds
    # is_superadmin. Set in Railway env vars, run migration, then remove.
    ADMIN_SUPERADMIN_USERNAME: str = ""
    ADMIN_SUPERADMIN_PASSWORD: str = ""

    EXTRACTION_STRATEGY: Literal["html_only", "vision_full", "hybrid", "gmb_first"] = "html_only"
    SALES_AGENT_BACKEND: Literal[
        "null", "console", "smartlead", "instantly", "smtp", "postmark"
    ] = "null"

    SCANNER_PASS_THRESHOLD: int = Field(default=60, ge=0, le=100)
    PREVIEW_EXPIRY_HOURS: int = Field(default=48, ge=1)
    FOLLOWUP_DELAY_HOURS: int = Field(default=24, ge=1)

    @field_validator("DATABASE_URL")
    @classmethod
    def _force_psycopg_v3(cls, v: str) -> str:
        # Railway + Supabase hand out bare postgresql:// URLs. SQLAlchemy's
        # default driver for that scheme is psycopg2 — we use psycopg v3.
        # Normalize both common prefixes so callers don't need to think about it.
        if v.startswith("postgresql+"):
            return v
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Import this, not the class directly."""
    return Settings()  # type: ignore[call-arg]
