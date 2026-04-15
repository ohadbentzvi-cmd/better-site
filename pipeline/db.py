"""SQLAlchemy engine + session factory.

One process-wide engine, cached lazily so importing this module doesn't
require a live DB. Sessions are short-lived — open one per flow run / task,
commit, close.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from pipeline.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    # Small pool — the worker is a single process; scale via replicas, not pool size.
    return create_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=2,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def session_scope() -> Session:
    """Open a new session. Caller is responsible for commit/rollback/close."""
    return _session_factory()()
