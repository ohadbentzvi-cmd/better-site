"""Stripe webhook handler.

CRITICAL: every incoming webhook MUST have its signature verified via
``stripe.Webhook.construct_event`` before any state change. Unsigned or
invalid-signature requests return 401 and are dropped.

Idempotency: the unique constraint on ``payments.stripe_payment_intent_id``
makes re-delivery safe — the second insert raises IntegrityError which the
handler catches and treats as a successful no-op.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.post("")
async def handle_stripe_webhook(request: Request) -> dict[str, str]:
    """Phase 4 implementation TODO.

    1. Read raw body (required for signature verification)
    2. stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
    3. dispatch on event.type:
         - payment_intent.succeeded → UPSERT payments, update lead status
         - charge.refunded → update payments + lead
         - charge.dispute.created → update payments + alert
    4. Return 200 to ack; Stripe will retry on any non-2xx
    """
    raise HTTPException(status_code=501, detail="stripe webhook not yet implemented")
