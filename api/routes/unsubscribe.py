"""Unsubscribe endpoint.

Writes the recipient's email to ``suppression_list`` with reason=unsubscribe.
Legally required under CAN-SPAM — must be accessible with one click from
every cold email.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("")
def unsubscribe(email: str) -> dict[str, bool]:
    """Phase 4 implementation TODO.

    1. Lowercase + trim email
    2. UPSERT into suppression_list (reason=unsubscribe)
    3. Update any lead with this email → status=unsubscribed
    4. Return {"ok": True}
    """
    raise HTTPException(status_code=501, detail="unsubscribe not yet implemented")
