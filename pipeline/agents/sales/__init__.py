"""Sales Agent — pluggable backend pattern.

Importing this module registers every shipped backend on the registry.
"""

from pipeline.agents.sales.base import (
    SalesAgentBackend,
    SalesAgentBackendError,
    SendResult,
    SendStatus,
)
from pipeline.agents.sales.registry import get_backend, list_backends
from pipeline.agents.sales.backends import (  # noqa: F401 — registration side-effects
    console_backend,
    null_backend,
)

__all__ = [
    "SalesAgentBackend",
    "SalesAgentBackendError",
    "SendResult",
    "SendStatus",
    "get_backend",
    "list_backends",
]
