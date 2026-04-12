"""Preview page data endpoint.

The Next.js ``/preview/[slug]`` route fetches from here to get the
extraction + scan + site row for rendering the personalized preview.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/{slug}")
def get_preview(slug: str) -> dict[str, object]:
    """Phase 4 implementation TODO.

    1. SELECT site JOIN extraction JOIN scan JOIN lead WHERE site.slug = :slug
    2. If site.expires_at < now() → 404
    3. Sanitize extracted HTML fields with bleach before returning
    4. Return JSON payload matching the Next.js PreviewPageData type
    """
    raise HTTPException(status_code=501, detail="preview endpoint not yet implemented")
