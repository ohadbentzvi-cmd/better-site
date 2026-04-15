"""Admin authentication primitives.

Split of responsibility:
    * Next.js web owns the signed session cookie. That's what the browser sees.
    * FastAPI trusts a shared service token (ADMIN_SERVICE_TOKEN) on every
      /admin/* request plus an X-Analyst-Id header identifying which analyst
      the web tier resolved from the cookie.

/admin/auth/verify is the one exception — it's a public endpoint that the
Next.js login flow calls server-to-server. It takes username+password,
checks bcrypt, and returns the analyst id. It is protected by its own
Postgres-backed rate limiter (not the service-token dep).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pipeline.config import get_settings
from pipeline.db import session_scope
from pipeline.models.analyst import Analyst, LoginAttempt

log = structlog.get_logger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# Fixed dummy hash used to equalize login timing when the username is unknown
# or the account is inactive. Prevents username enumeration via response-time
# side-channel. The plaintext is unrelated to any real password.
_DUMMY_HASH = _pwd_context.hash("bettersite-timing-equalizer-v1")


class AuthError(HTTPException):
    """401 with a generic body. Never leaks which branch failed."""

    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class RateLimitError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Wait and try again.",
        )


# ── Password hashing ────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


# ── Session dependency for /api/admin/* ─────────────────────────────────────
def require_service_token(
    x_service_token: Annotated[str | None, Header()] = None,
) -> None:
    """Reject any /admin/* request without a matching service token."""
    settings = get_settings()
    expected = settings.ADMIN_SERVICE_TOKEN
    if not expected:
        # Deployment misconfig: refuse rather than quietly allow.
        raise AuthError("Admin service token not configured")
    if not x_service_token or x_service_token != expected:
        raise AuthError()


def require_analyst(
    x_analyst_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """Resolve the analyst UUID from the X-Analyst-Id header.

    The web tier sets this header after verifying the session cookie. FastAPI
    validates that the UUID parses and corresponds to an active analyst.
    """
    if not x_analyst_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Analyst-Id header",
        )
    try:
        analyst_id = uuid.UUID(x_analyst_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Analyst-Id header",
        ) from e

    session: Session = session_scope()
    try:
        row = session.scalar(
            select(Analyst).where(Analyst.id == analyst_id, Analyst.active.is_(True))
        )
    finally:
        session.close()
    if row is None:
        raise AuthError("Analyst not found or inactive")
    return analyst_id


AnalystId = Annotated[uuid.UUID, Depends(require_analyst)]
ServiceToken = Annotated[None, Depends(require_service_token)]


# ── /auth/verify — the one public endpoint ──────────────────────────────────
def _count_recent_failures(session: Session, username: str) -> int:
    settings = get_settings()
    window_start = datetime.now(tz=timezone.utc) - timedelta(
        minutes=settings.ADMIN_LOGIN_RATE_LIMIT_WINDOW_MIN
    )
    return int(
        session.scalar(
            select(func.count(LoginAttempt.id)).where(
                LoginAttempt.username == username,
                LoginAttempt.success.is_(False),
                LoginAttempt.attempt_at >= window_start,
            )
        )
        or 0
    )


def authenticate_analyst(username: str, password: str) -> Analyst:
    """Rate-limited bcrypt compare.

    Raises:
        RateLimitError: the username is over the 15-min failure budget.
        AuthError: bad password / unknown username / inactive analyst.
            All three collapse to the same 401 body — no enumeration.
    """
    settings = get_settings()
    session: Session = session_scope()
    try:
        # Rate limit BEFORE bcrypt. Don't waste CPU on a known-attacking username.
        recent_failures = _count_recent_failures(session, username)
        if recent_failures >= settings.ADMIN_LOGIN_RATE_LIMIT_MAX_FAILURES:
            session.add(
                LoginAttempt(username=username, success=False)
            )
            session.commit()
            log.warning("admin_login_rate_limited", username=username)
            raise RateLimitError()

        analyst = session.scalar(
            select(Analyst).where(Analyst.username == username)
        )

        # Always run bcrypt, even for unknown or inactive accounts, so response
        # time doesn't leak which branch we're on. The comparison result for
        # the dummy hash is discarded.
        if analyst is not None and analyst.active:
            password_ok = verify_password(password, analyst.password_hash)
        else:
            verify_password(password, _DUMMY_HASH)
            password_ok = False

        valid = analyst is not None and analyst.active and password_ok

        session.add(LoginAttempt(username=username, success=valid))
        if valid and analyst is not None:
            analyst.last_login_at = datetime.now(tz=timezone.utc)
        session.commit()

        if not valid:
            log.info("admin_login_failed", username=username)
            raise AuthError("Username or password is incorrect")

        # Detach from the session so caller can read attrs after we close it.
        assert analyst is not None
        session.refresh(analyst)
        session.expunge(analyst)
        log.info("admin_login_succeeded", analyst_id=str(analyst.id), username=username)
        return analyst
    finally:
        session.close()
