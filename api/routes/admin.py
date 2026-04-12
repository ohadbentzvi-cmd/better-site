"""Internal admin routes: leads view, review queue, cost dashboard.

All routes require HTTP basic auth via the ADMIN_BASIC_AUTH_USER and
ADMIN_BASIC_AUTH_PASSWORD env vars.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/leads")
def list_leads() -> dict[str, object]:
    """Phase 5 implementation TODO.

    Paginated list of leads with filters by status/vertical/country.
    """
    raise HTTPException(status_code=501, detail="admin/leads not yet implemented")


@router.get("/review-queue")
def review_queue() -> dict[str, object]:
    """Phase 5 implementation TODO.

    Leads in status=review_pending with their preview URL + scan issues.
    """
    raise HTTPException(status_code=501, detail="admin/review-queue not yet implemented")


@router.post("/review-queue/{lead_id}/approve")
def approve_lead(lead_id: str) -> dict[str, bool]:
    """Phase 5 implementation TODO.

    Idempotent: safe to call twice. Transitions lead to approved + enqueues send.
    """
    raise HTTPException(status_code=501, detail="admin/approve not yet implemented")


@router.get("/costs")
def cost_dashboard() -> dict[str, object]:
    """Phase 5 implementation TODO.

    Daily spend per external service (Claude / Hunter / ZeroBounce /
    PageSpeed) by reading from the ``events`` table.
    """
    raise HTTPException(status_code=501, detail="admin/costs not yet implemented")
