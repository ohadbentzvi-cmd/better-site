"""Console sending backend — prints the email to stdout.

Useful for local testing and for the Phase 5 pre-flight when comparing
rendered output against the real provider's output.
"""

from __future__ import annotations

import structlog

from pipeline.agents.sales.base import (
    SalesAgentBackend,
    SendPayload,
    SendResult,
    SendStatus,
)
from pipeline.agents.sales.registry import register

log = structlog.get_logger(__name__)


@register
class ConsoleSalesAgentBackend(SalesAgentBackend):
    name = "console"

    def send(self, payload: SendPayload) -> SendResult:
        log.info(
            "console_backend_send",
            to=payload.recipient_email,
            subject=payload.subject,
            body_length=len(payload.html_body),
            tracking_token=payload.tracking_token,
        )
        return SendResult(
            status=SendStatus.sent,
            backend_name=self.name,
            inbox_used="stdout",
            provider_message_id=f"console-{payload.tracking_token}",
            error_message=None,
            raw_response={},
        )
