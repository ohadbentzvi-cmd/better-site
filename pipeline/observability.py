"""Logging bootstrap so structlog output reaches the Prefect UI.

structlog's default ``PrintLoggerFactory`` writes to stderr directly, which
bypasses Python's ``logging`` module — which is what Prefect intercepts for
its run log viewer. We reconfigure structlog to go through stdlib logging
so Prefect can capture every event.

Two-part setup:

1. ``configure()`` — call once at process startup. Swaps structlog's factory
   to ``stdlib.LoggerFactory`` and wires a basic root handler.
2. ``PREFECT_LOGGING_EXTRA_LOGGERS=pipeline`` — env var set in
   ``pipeline/deploy.py`` before any Prefect import, telling Prefect to
   attach its log handler to the ``pipeline.*`` logger hierarchy.
"""

from __future__ import annotations

import logging
import sys

import structlog

_configured = False


def configure(level: int = logging.INFO) -> None:
    """Route structlog through stdlib logging. Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stderr,
        force=False,
    )
    logging.getLogger("pipeline").setLevel(level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
