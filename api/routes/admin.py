"""Admin Review Console routes.

Shape:
    POST  /admin/auth/verify          — public; rate-limited bcrypt compare
    POST  /admin/auth/change-password — any analyst can change their own password
    POST  /admin/analysts             — superadmin creates a new analyst
    GET   /admin/leads                — paginated list, filters + search
    GET   /admin/leads/{id}           — full detail + review history
    POST  /admin/leads/{id}/review    — approve/reject (append-only)
    POST  /admin/leads/{id}/email     — backfill email; flips email_source to 'manual'
    POST  /admin/scans/{id}/review    — free-text scan feedback (append-only)

All routes except /auth/verify require a matching X-Service-Token header.
Mutating routes additionally require X-Analyst-Id.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import (
    AnalystId,
    ServiceToken,
    SuperadminId,
    authenticate_analyst,
    hash_password,
    verify_password,
)
from api.schemas.admin import (
    ChangePasswordRequest,
    CreateAnalystRequest,
    CreateAnalystResponse,
    EmailBackfillRequest,
    LeadDetail,
    LeadReviewOut,
    LeadReviewSummary,
    LeadRow,
    LeadsListResponse,
    ReviewCreate,
    ReviewedOut,
    ScanDetail,
    ScanFeedbackCreate,
    ScanReviewOut,
    ScanSummary,
    VerifyRequest,
    VerifyResponse,
    project_key_metrics,
)
from pipeline.db import session_scope
from pipeline.models.analyst import Analyst
from pipeline.models.event import Event
from pipeline.models.lead import Lead, LeadStatus
from pipeline.models.review import (
    LeadReview,
    LeadReviewReason,
    LeadReviewVerdict,
    ScanReview,
)
from pipeline.models.scan import Scan

log = structlog.get_logger(__name__)

router = APIRouter()


# ── /auth/verify (PUBLIC) ───────────────────────────────────────────────────
@router.post("/auth/verify", response_model=VerifyResponse)
def verify_credentials(body: VerifyRequest) -> VerifyResponse:
    """Server-to-server credential check for the Next.js login flow.

    Intentionally not behind the service-token guard — this is the only
    endpoint callable without an already-established identity. It has its
    own rate limiter and its own generic 401 body.
    """
    analyst = authenticate_analyst(body.username, body.password)
    return VerifyResponse(
        analyst_id=analyst.id,
        username=analyst.username,
        is_superadmin=analyst.is_superadmin,
    )


# ── /auth/change-password ───────────────────────────────────────────────────
@router.post("/auth/change-password", response_model=ReviewedOut)
def change_password(
    body: ChangePasswordRequest,
    _: ServiceToken,
    analyst_id: AnalystId,
) -> ReviewedOut:
    """Any analyst can change their own password."""
    session: Session = session_scope()
    try:
        analyst = session.scalar(
            select(Analyst).where(Analyst.id == analyst_id, Analyst.active.is_(True))
        )
        if analyst is None:
            raise HTTPException(status_code=404, detail="Analyst not found")

        if not verify_password(body.current_password, analyst.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )

        analyst.password_hash = hash_password(body.new_password)
        session.commit()
        log.info("password_changed", analyst_id=str(analyst_id))
        return ReviewedOut(id=analyst_id)
    finally:
        session.close()


# ── /analysts (POST, superadmin only) ───────────────────────────────────────
@router.post(
    "/analysts",
    response_model=CreateAnalystResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_analyst(
    body: CreateAnalystRequest,
    _: ServiceToken,
    __: SuperadminId,
) -> CreateAnalystResponse:
    """Only superadmins can create new analyst accounts."""
    session: Session = session_scope()
    try:
        existing = session.scalar(
            select(Analyst).where(Analyst.username == body.username)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Analyst '{body.username}' already exists",
            )

        analyst = Analyst(
            id=uuid.uuid4(),
            username=body.username,
            password_hash=hash_password(body.password),
            active=True,
            is_superadmin=False,
        )
        session.add(analyst)
        session.commit()
        log.info(
            "analyst_created",
            new_analyst_id=str(analyst.id),
            new_username=body.username,
        )
        return CreateAnalystResponse(analyst_id=analyst.id, username=analyst.username)
    finally:
        session.close()


# ── Helpers ─────────────────────────────────────────────────────────────────
def _is_check_violation(err: IntegrityError, constraint: str) -> bool:
    msg = str(err.orig) if err.orig else str(err)
    return constraint in msg


def _lead_row_from_query(row: Any) -> LeadRow:
    scan = None
    if row.scan_id is not None:
        scan = ScanSummary(
            id=row.scan_id,
            score=row.scan_score,
            score_performance=row.scan_perf,
            score_seo=row.scan_seo,
            score_ai_readiness=row.scan_ai,
            score_security=row.scan_sec,
            scan_partial=row.scan_partial,
            pass_fail=row.scan_pass_fail,
        )

    latest_review = None
    if row.review_id is not None:
        latest_review = LeadReviewSummary(
            id=row.review_id,
            verdict=LeadReviewVerdict(row.review_verdict),
            reason_code=(
                LeadReviewReason(row.review_reason) if row.review_reason else None
            ),
            analyst_username=row.review_analyst_username or "unknown",
            created_at=row.review_created_at,
        )

    return LeadRow(
        id=row.id,
        business_name=row.business_name,
        canonical_domain=row.canonical_domain,
        website_url=row.website_url,
        vertical=row.vertical,
        country=row.country,
        status=LeadStatus(row.status),
        email=row.email,
        email_source=row.email_source,
        created_at=row.created_at,
        scan=scan,
        latest_review=latest_review,
    )


def _build_cursor(created_at: datetime, lead_id: uuid.UUID) -> str:
    return f"{created_at.isoformat()}_{lead_id}"


def _parse_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not cursor:
        return None
    try:
        ts_str, id_str = cursor.rsplit("_", 1)
        return datetime.fromisoformat(ts_str), uuid.UUID(id_str)
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cursor",
        ) from e


# ── /leads (GET, list) ──────────────────────────────────────────────────────
@router.get("/leads", response_model=LeadsListResponse)
def list_leads(
    _: ServiceToken,
    __: AnalystId,
    status_: LeadStatus | None = Query(default=None, alias="status"),
    vertical: str | None = Query(default=None),
    score_min: int | None = Query(default=None, ge=0, le=100),
    score_max: int | None = Query(default=None, ge=0, le=100),
    reviewed: bool | None = Query(default=None),
    has_email: bool | None = Query(default=None),
    q: str | None = Query(default=None, max_length=128),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> LeadsListResponse:
    """One SQL query for the page. One COUNT query for the total.

    The COUNT excludes the cursor clause so "total" reflects the filtered
    dataset, not a per-page remainder.
    """
    parsed_cursor = _parse_cursor(cursor)

    # Filter clauses shared by page query and count query. Cursor is NOT here.
    filter_clauses: list[str] = []
    filter_params: dict[str, Any] = {}
    if status_:
        filter_clauses.append("l.status = :status")
        filter_params["status"] = status_.value
    if vertical:
        filter_clauses.append("l.vertical = :vertical")
        filter_params["vertical"] = vertical
    if score_min is not None:
        filter_clauses.append("s.score >= :score_min")
        filter_params["score_min"] = score_min
    if score_max is not None:
        filter_clauses.append("s.score <= :score_max")
        filter_params["score_max"] = score_max
    if has_email is True:
        filter_clauses.append("l.email IS NOT NULL")
    elif has_email is False:
        filter_clauses.append("l.email IS NULL")
    if reviewed is True:
        filter_clauses.append("lr.id IS NOT NULL")
    elif reviewed is False:
        filter_clauses.append("lr.id IS NULL")
    if q:
        filter_clauses.append(
            "(l.business_name ILIKE :q OR l.canonical_domain ILIKE :q)"
        )
        filter_params["q"] = f"%{q}%"

    page_clauses = list(filter_clauses)
    page_params: dict[str, Any] = {**filter_params, "limit": limit + 1}
    if parsed_cursor is not None:
        page_clauses.append("(l.created_at, l.id) < (:cur_ts, :cur_id)")
        page_params["cur_ts"] = parsed_cursor[0]
        page_params["cur_id"] = parsed_cursor[1]

    filter_where = (
        " AND " + " AND ".join(filter_clauses) if filter_clauses else ""
    )
    page_where = (" AND " + " AND ".join(page_clauses)) if page_clauses else ""

    page_sql = text(
        f"""
        SELECT
            l.id, l.business_name, l.canonical_domain, l.website_url,
            l.vertical, l.country, l.status, l.email, l.email_source,
            l.created_at,
            s.id AS scan_id,
            s.score AS scan_score,
            s.score_performance AS scan_perf,
            s.score_seo AS scan_seo,
            s.score_ai_readiness AS scan_ai,
            s.score_security AS scan_sec,
            s.scan_partial AS scan_partial,
            s.pass_fail AS scan_pass_fail,
            lr.id AS review_id,
            lr.verdict AS review_verdict,
            lr.reason_code AS review_reason,
            lr.created_at AS review_created_at,
            a.username AS review_analyst_username
        FROM ops.leads l
        LEFT JOIN ops.scans s ON s.lead_id = l.id
        LEFT JOIN LATERAL (
            SELECT lr.id, lr.verdict, lr.reason_code, lr.created_at, lr.analyst_id
            FROM ops.lead_reviews lr
            WHERE lr.lead_id = l.id
            ORDER BY lr.created_at DESC
            LIMIT 1
        ) lr ON true
        LEFT JOIN ops.analysts a ON a.id = lr.analyst_id
        WHERE 1=1 {page_where}
        ORDER BY l.created_at DESC, l.id DESC
        LIMIT :limit
        """
    )

    count_sql = text(
        f"""
        SELECT COUNT(*) AS n
        FROM ops.leads l
        LEFT JOIN ops.scans s ON s.lead_id = l.id
        LEFT JOIN LATERAL (
            SELECT lr.id FROM ops.lead_reviews lr
            WHERE lr.lead_id = l.id
            ORDER BY lr.created_at DESC LIMIT 1
        ) lr ON true
        WHERE 1=1 {filter_where}
        """
    )

    session: Session = session_scope()
    try:
        rows = session.execute(page_sql, page_params).fetchall()
        total = int(session.execute(count_sql, filter_params).scalar() or 0)
    finally:
        session.close()

    items = [_lead_row_from_query(r) for r in rows[:limit]]
    next_cursor = None
    if len(rows) > limit and items:
        last = items[-1]
        next_cursor = _build_cursor(last.created_at, last.id)

    return LeadsListResponse(items=items, next_cursor=next_cursor, total=total)


# ── /leads/{id} (GET, detail) ───────────────────────────────────────────────
@router.get("/leads/{lead_id}", response_model=LeadDetail)
def get_lead(
    lead_id: uuid.UUID,
    _: ServiceToken,
    __: AnalystId,
) -> LeadDetail:
    session: Session = session_scope()
    try:
        lead = session.scalar(select(Lead).where(Lead.id == lead_id))
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")

        scan = session.scalar(select(Scan).where(Scan.lead_id == lead_id))

        lead_reviews_rows = (
            session.execute(
                text(
                    """
                    SELECT lr.id, lr.verdict, lr.reason_code, lr.note, lr.created_at,
                           a.username AS analyst_username
                    FROM ops.lead_reviews lr
                    JOIN ops.analysts a ON a.id = lr.analyst_id
                    WHERE lr.lead_id = :lead_id
                    ORDER BY lr.created_at DESC
                    """
                ),
                {"lead_id": lead_id},
            )
            .mappings()
            .all()
        )

        scan_review_rows: list[dict[str, Any]] = []
        scan_detail: ScanDetail | None = None
        if scan is not None:
            scan_review_rows = list(
                session.execute(
                    text(
                        """
                        SELECT sr.id, sr.reasoning, sr.created_at,
                               a.username AS analyst_username
                        FROM ops.scan_reviews sr
                        JOIN ops.analysts a ON a.id = sr.analyst_id
                        WHERE sr.scan_id = :scan_id
                        ORDER BY sr.created_at DESC
                        """
                    ),
                    {"scan_id": scan.id},
                )
                .mappings()
                .all()
            )
            scan_detail = ScanDetail(
                id=scan.id,
                score=scan.score,
                score_performance=scan.score_performance,
                score_seo=scan.score_seo,
                score_ai_readiness=scan.score_ai_readiness,
                score_security=scan.score_security,
                scan_partial=scan.scan_partial,
                pass_fail=scan.pass_fail,
                scanned_url=scan.scanned_url,
                issues=list(scan.issues_json or []),
                key_metrics=project_key_metrics(scan.raw_metrics),
                pagespeed_mobile=scan.pagespeed_mobile,
                pagespeed_desktop=scan.pagespeed_desktop,
                scanned_at=scan.created_at,
            )

        return LeadDetail(
            id=lead.id,
            business_name=lead.business_name,
            canonical_domain=lead.canonical_domain,
            website_url=lead.website_url,
            vertical=lead.vertical,
            city=lead.city,
            state=lead.state,
            country=lead.country,
            email=lead.email,
            email_source=lead.email_source,
            phone=lead.phone,
            source=lead.source,
            status=lead.status,
            created_at=lead.created_at,
            scan=scan_detail,
            lead_reviews=[LeadReviewOut(**dict(r)) for r in lead_reviews_rows],
            scan_reviews=[ScanReviewOut(**dict(r)) for r in scan_review_rows],
        )
    finally:
        session.close()


# ── /leads/{id}/review (POST) ───────────────────────────────────────────────
@router.post(
    "/leads/{lead_id}/review",
    response_model=ReviewedOut,
    status_code=status.HTTP_201_CREATED,
)
def create_lead_review(
    lead_id: uuid.UUID,
    body: ReviewCreate,
    _: ServiceToken,
    analyst_id: AnalystId,
) -> ReviewedOut:
    session: Session = session_scope()
    try:
        lead = session.scalar(select(Lead).where(Lead.id == lead_id))
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")

        review = LeadReview(
            lead_id=lead_id,
            analyst_id=analyst_id,
            verdict=body.verdict,
            reason_code=body.reason_code,
            note=body.note,
        )
        session.add(review)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            if _is_check_violation(e, "lead_review_verdict_shape"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "invalid_review_shape",
                        "message": (
                            "Rejected reviews require a reason_code; "
                            "'duplicate_or_other' also requires a note."
                        ),
                    },
                ) from e
            raise
        log.info(
            "lead_reviewed",
            lead_id=str(lead_id),
            analyst_id=str(analyst_id),
            verdict=body.verdict.value,
            reason_code=body.reason_code.value if body.reason_code else None,
        )
        return ReviewedOut(id=review.id)
    finally:
        session.close()


# ── /leads/{id}/email (POST) ────────────────────────────────────────────────
@router.post("/leads/{lead_id}/email", response_model=ReviewedOut)
def backfill_email(
    lead_id: uuid.UUID,
    body: EmailBackfillRequest,
    _: ServiceToken,
    analyst_id: AnalystId,
) -> ReviewedOut:
    """Atomic UPDATE. 409 if email already set (racing analysts are safe)."""
    session: Session = session_scope()
    try:
        result = session.execute(
            text(
                """
                UPDATE ops.leads
                SET email = :email,
                    email_source = 'manual',
                    updated_at = NOW()
                WHERE id = :lead_id AND email IS NULL
                RETURNING id
                """
            ),
            {"email": str(body.email), "lead_id": lead_id},
        ).first()

        if result is None:
            exists = session.scalar(select(Lead.id).where(Lead.id == lead_id))
            if not exists:
                raise HTTPException(status_code=404, detail="Lead not found")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already set for this lead",
            )

        session.add(
            Event(
                lead_id=lead_id,
                event_type="email_backfilled",
                payload={
                    "analyst_id": str(analyst_id),
                    "email": str(body.email),
                },
            )
        )
        session.commit()
        log.info("email_backfilled", lead_id=str(lead_id), analyst_id=str(analyst_id))
        return ReviewedOut(id=lead_id)
    finally:
        session.close()


# ── /scans/{id}/review (POST) ───────────────────────────────────────────────
@router.post(
    "/scans/{scan_id}/review",
    response_model=ReviewedOut,
    status_code=status.HTTP_201_CREATED,
)
def create_scan_review(
    scan_id: uuid.UUID,
    body: ScanFeedbackCreate,
    _: ServiceToken,
    analyst_id: AnalystId,
) -> ReviewedOut:
    session: Session = session_scope()
    try:
        scan = session.scalar(select(Scan).where(Scan.id == scan_id))
        if scan is None:
            raise HTTPException(status_code=404, detail="Scan not found")

        review = ScanReview(
            scan_id=scan_id,
            analyst_id=analyst_id,
            reasoning=body.reasoning,
        )
        session.add(review)
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            if _is_check_violation(e, "scan_review_reasoning_nonempty"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "empty_reasoning"},
                ) from e
            raise
        log.info(
            "scan_feedback_submitted",
            scan_id=str(scan_id),
            analyst_id=str(analyst_id),
            length=len(body.reasoning),
        )
        return ReviewedOut(id=review.id)
    finally:
        session.close()
