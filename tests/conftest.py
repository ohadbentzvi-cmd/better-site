"""Shared pytest fixtures for the BetterSite pipeline and API tests."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
