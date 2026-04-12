"""FastAPI app entrypoint.

Run locally (against Railway staging):
    cd api && uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import admin, preview, stripe_webhooks, unsubscribe
from pipeline.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()


app = FastAPI(
    title="BetterSite API",
    version="0.0.2",
    description="Backend for the Next.js app + Stripe webhooks.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.APP_BASE_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(preview.router, prefix="/preview", tags=["preview"])
app.include_router(stripe_webhooks.router, prefix="/webhooks/stripe", tags=["stripe"])
app.include_router(unsubscribe.router, prefix="/unsubscribe", tags=["unsubscribe"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.0.2", "env": settings.APP_ENV}
