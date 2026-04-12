"""Null sending backend — records the send attempt but never actually sends.

Used in v0 and in tests. The ``emails`` row is still written by the
surrounding Sales Agent flow, so the dashboard sees the send attempt and
state transitions happen normally.
"""

from __future__ import annotations

from pipeline.agents.sales.base import (
    SalesAgentBackend,
    SendPayload,
    SendResult,
    SendStatus,
)
from pipeline.agents.sales.registry import register


@register
class NullSalesAgentBackend(SalesAgentBackend):
    name = "null"

    def send(self, payload: SendPayload) -> SendResult:
        return SendResult(
            status=SendStatus.skipped,
            backend_name=self.name,
            inbox_used=None,
            provider_message_id=None,
            error_message=None,
            raw_response={"skipped": True, "reason": "null backend"},
        )
