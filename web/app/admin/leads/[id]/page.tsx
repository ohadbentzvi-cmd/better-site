import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { DimensionScores } from "@/components/admin/dimension-scores";
import { EmailBackfillForm } from "@/components/admin/email-backfill-form";
import { IssueList } from "@/components/admin/issue-list";
import { MetricsGrid } from "@/components/admin/metrics-grid";
import { ReviewForm } from "@/components/admin/review-form";
import { ReviewHistory } from "@/components/admin/review-history";
import { ScanFeedbackForm } from "@/components/admin/scan-feedback-form";
import { ScoreBar } from "@/components/admin/score-bar";
import { apiFetch, ApiError } from "@/lib/admin/api";
import { SESSION_COOKIE_NAME, verifySession } from "@/lib/admin/session";

export const dynamic = "force-dynamic";

interface LeadDetail {
  id: string;
  business_name: string;
  canonical_domain: string;
  website_url: string;
  vertical: string;
  city: string | null;
  state: string | null;
  country: string;
  email: string | null;
  email_source: string | null;
  phone: string | null;
  source: string;
  status: string;
  created_at: string;
  scan: {
    id: string;
    score: number | null;
    score_performance: number | null;
    score_seo: number | null;
    score_ai_readiness: number | null;
    score_security: number | null;
    scan_partial: boolean;
    pass_fail: boolean;
    scanned_url: string | null;
    issues: Array<Record<string, unknown>>;
    key_metrics: Record<string, unknown>;
    pagespeed_mobile: number | null;
    pagespeed_desktop: number | null;
    scanned_at: string;
  } | null;
  lead_reviews: Array<{
    id: string;
    verdict: "approved" | "rejected";
    reason_code: string | null;
    note: string | null;
    analyst_username: string;
    created_at: string;
  }>;
  scan_reviews: Array<{
    id: string;
    reasoning: string;
    analyst_username: string;
    created_at: string;
  }>;
}

function fmtLocation(city: string | null, state: string | null, country: string) {
  return [city, state, country].filter(Boolean).join(", ");
}

export default async function LeadDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const token = cookies().get(SESSION_COOKIE_NAME)?.value;
  const session = token ? await verifySession(token) : null;
  if (!session) return null;

  let lead: LeadDetail | null = null;
  try {
    lead = await apiFetch<LeadDetail>(`/admin/leads/${params.id}`, { session });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    return (
      <div className="py-12">
        <PageHeader title="Lead" />
        <div
          className="flex items-center gap-2 p-3 border border-[var(--danger-soft)] bg-[var(--danger-soft)] text-[var(--danger)] rounded-md text-sm"
          role="alert"
        >
          <AlertCircle size={16} aria-hidden="true" />
          Couldn&apos;t load this lead.
        </div>
      </div>
    );
  }

  if (!lead) return null;

  return (
    <>
      <PageHeader
        title={lead.business_name}
        subtitle={
          <span className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs">{lead.canonical_domain}</span>
            <span>·</span>
            <span>{lead.vertical}</span>
            <span>·</span>
            <span>{fmtLocation(lead.city, lead.state, lead.country)}</span>
            <Badge variant="neutral">{lead.status}</Badge>
            {lead.scan?.scan_partial ? (
              <Badge variant="warning">Partial scan</Badge>
            ) : null}
          </span>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6 pb-12">
        {/* ─── Left: scan + email ──────────────────────────────────── */}
        <div className="space-y-5 min-w-0">
          <Card>
            <CardHeader>Contact</CardHeader>
            <CardBody>
              <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
                <dt className="text-[var(--text-secondary)]">Email</dt>
                <dd className="text-[var(--text-primary)]">
                  {lead.email ? (
                    <>
                      <span className="font-mono">{lead.email}</span>
                      {lead.email_source ? (
                        <span className="ml-2 text-xs text-[var(--text-tertiary)]">
                          ({lead.email_source})
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <span className="text-[var(--text-tertiary)]">—</span>
                  )}
                </dd>
                <dt className="text-[var(--text-secondary)]">Phone</dt>
                <dd className="text-[var(--text-primary)]">
                  {lead.phone || (
                    <span className="text-[var(--text-tertiary)]">—</span>
                  )}
                </dd>
                <dt className="text-[var(--text-secondary)]">Website</dt>
                <dd>
                  <a
                    href={lead.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[var(--accent)] hover:underline font-mono text-xs"
                  >
                    {lead.website_url}
                  </a>
                </dd>
                <dt className="text-[var(--text-secondary)]">Source</dt>
                <dd className="text-[var(--text-secondary)] text-xs uppercase tracking-wide">
                  {lead.source}
                </dd>
              </dl>

              {lead.email === null ? (
                <div className="mt-4 pt-4 border-t border-[var(--surface-3)]">
                  <EmailBackfillForm leadId={lead.id} />
                </div>
              ) : null}
            </CardBody>
          </Card>

          {lead.scan ? (
            <Card>
              <CardHeader>Scan</CardHeader>
              <CardBody className="space-y-5">
                <div>
                  <div className="flex items-center gap-4">
                    <ScoreBar
                      score={lead.scan.score}
                      partial={lead.scan.scan_partial}
                      width={240}
                    />
                    {lead.scan.pass_fail ? (
                      <Badge variant="success">pass</Badge>
                    ) : (
                      <Badge variant="danger">fail</Badge>
                    )}
                  </div>
                  {lead.scan.scanned_url ? (
                    <div className="mt-2 text-xs text-[var(--text-tertiary)] font-mono">
                      {lead.scan.scanned_url}
                    </div>
                  ) : null}
                </div>

                <div>
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wide">
                    Dimensions
                  </div>
                  <DimensionScores
                    performance={lead.scan.score_performance}
                    seo={lead.scan.score_seo}
                    aiReadiness={lead.scan.score_ai_readiness}
                    security={lead.scan.score_security}
                  />
                </div>

                {Object.keys(lead.scan.key_metrics).length > 0 ? (
                  <div>
                    <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wide">
                      Key metrics
                    </div>
                    <MetricsGrid metrics={lead.scan.key_metrics} />
                  </div>
                ) : null}

                <div>
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wide">
                    Issues
                  </div>
                  <IssueList issues={lead.scan.issues} />
                </div>

                <div className="pt-3 border-t border-[var(--surface-3)]">
                  <ScanFeedbackForm scanId={lead.scan.id} />
                </div>
              </CardBody>
            </Card>
          ) : (
            <Card>
              <CardHeader>Scan</CardHeader>
              <CardBody>
                <p className="text-sm text-[var(--text-secondary)]">
                  This lead hasn&apos;t been scanned yet.
                </p>
              </CardBody>
            </Card>
          )}
        </div>

        {/* ─── Right: review + history ─────────────────────────────── */}
        <div className="space-y-5 min-w-0 xl:sticky xl:top-4 xl:self-start">
          <Card>
            <CardHeader>Review</CardHeader>
            <CardBody>
              <ReviewForm leadId={lead.id} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>History</CardHeader>
            <CardBody>
              <ReviewHistory
                leadReviews={lead.lead_reviews}
                scanReviews={lead.scan_reviews}
              />
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
