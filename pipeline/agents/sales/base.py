"""Sales Agent backend protocol.

A ``SalesAgentBackend`` knows how to deliver a rendered email to a lead.
The surrounding flow (ZeroBounce verification, suppression check, DB writes)
is backend-agnostic — backends only see the final rendered send payload.

The real backend (Smartlead / Instantly / SMTP / Postmark) is selected in
Phase 5 pre-flight. v0 ships ``null`` and ``console`` only.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class SendStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    deferred = "deferred"  # backend accepted but will retry later
    rejected = "rejected"  # backend permanently refused (bad address, 5xx, etc.)
    skipped = "skipped"  # null backend path


@dataclass(frozen=True)
class SendResult:
    status: SendStatus
    backend_name: str
    inbox_used: str | None = None
    provider_message_id: str | None = None
    error_message: str | None = None
    raw_response: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SendPayload:
    """Everything a backend needs to deliver one email.

    The Sales Agent flow is responsible for rendering the body + verifying
    the recipient before constructing this object.
    """

    recipient_email: str
    recipient_name: str | None
    from_name: str
    from_email: str | None  # optional — some backends manage this themselves
    reply_to: str | None
    subject: str
    html_body: str
    text_body: str | None  # plain-text fallback
    tracking_token: str  # used to match opens/clicks back to the lead


class SalesAgentBackend(ABC):
    """Abstract base for every sending backend."""

    name: str  # must be set on each concrete subclass

    @abstractmethod
    def send(self, payload: SendPayload) -> SendResult:
        """Deliver one email and return a SendResult.

        Must not raise on ordinary delivery failures — use
        ``SendStatus.rejected`` or ``SendStatus.deferred`` instead. Raise
        ``SalesAgentBackendError`` only for unrecoverable configuration /
        programmer errors.
        """


class SalesAgentBackendError(Exception):
    """Raised for unrecoverable backend failures (missing config, etc.)."""
