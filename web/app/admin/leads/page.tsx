import { cookies } from "next/headers";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { FilterBar } from "@/components/admin/filter-bar";
import { LeadsTable } from "@/components/admin/leads-table";
import { apiFetch, ApiError } from "@/lib/admin/api";
import { SESSION_COOKIE_NAME, verifySession } from "@/lib/admin/session";
import Link from "next/link";
import { Inbox, AlertCircle } from "lucide-react";

export const dynamic = "force-dynamic";

interface LeadRow {
  id: string;
  business_name: string;
  canonical_domain: string;
  website_url: string;
  vertical: string;
  country: string;
  status: string;
  email: string | null;
  email_source: string | null;
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
  } | null;
  latest_review: {
    id: string;
    verdict: "approved" | "rejected";
    reason_code: string | null;
    analyst_username: string;
    created_at: string;
  } | null;
}

interface LeadsResponse {
  items: LeadRow[];
  next_cursor: string | null;
  total: number;
}

interface SearchParams {
  [key: string]: string | string[] | undefined;
}

function buildQueryString(sp: SearchParams): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (typeof v === "string" && v.length > 0) params.set(k, v);
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

export default async function LeadsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const token = cookies().get(SESSION_COOKIE_NAME)?.value;
  const session = token ? await verifySession(token) : null;
  if (!session) {
    return null; // middleware redirects; this is a safety net.
  }

  let data: LeadsResponse | null = null;
  let errorMessage: string | null = null;
  try {
    data = await apiFetch<LeadsResponse>(
      `/admin/leads${buildQueryString(searchParams)}`,
      { session },
    );
  } catch (err) {
    errorMessage =
      err instanceof ApiError && err.status === 400
        ? "One of the filters is invalid."
        : "Couldn't load leads.";
  }

  const hasFilters = Object.keys(searchParams).some(
    (k) => k !== "cursor" && searchParams[k],
  );
  const isPaginated = typeof searchParams.cursor === "string" && searchParams.cursor.length > 0;
  const totalLabel = data
    ? `${data.total.toLocaleString()} ${data.total === 1 ? "lead" : "leads"}${hasFilters ? " matching filters" : ""}`
    : null;

  return (
    <>
      <PageHeader title="Leads" subtitle={totalLabel} />
      <FilterBar />

      {errorMessage ? (
        <div
          className="mt-4 flex items-center justify-between gap-4 p-3 border border-[var(--danger-soft)] bg-[var(--danger-soft)] text-[var(--danger)] rounded-md text-sm"
          role="alert"
        >
          <div className="flex items-center gap-2">
            <AlertCircle size={16} aria-hidden="true" />
            {errorMessage}
          </div>
        </div>
      ) : null}

      {data && data.items.length > 0 ? (
        <LeadsTable rows={data.items} />
      ) : data && data.items.length === 0 ? (
        <EmptyState
          icon={<Inbox size={28} />}
          title={hasFilters ? "No leads match these filters." : "No leads yet."}
          description={
            hasFilters
              ? "Adjust the filters to see more leads."
              : "Leads will appear here as the Lead Generator ingests them."
          }
          action={
            hasFilters ? (
              <Link href="/admin/leads">
                <Button variant="ghost">Clear filters</Button>
              </Link>
            ) : null
          }
        />
      ) : null}

      {data && (data.next_cursor || isPaginated) ? (
        <div className="py-4 flex items-center justify-between text-sm text-[var(--text-secondary)]">
          <span>
            {isPaginated ? "Showing more leads from the filtered set." : null}
          </span>
          <div className="flex items-center gap-2">
            {isPaginated ? (
              <Link
                href={`/admin/leads${buildQueryString({
                  ...searchParams,
                  cursor: undefined,
                })}`}
              >
                <Button variant="ghost">Back to first page</Button>
              </Link>
            ) : null}
            {data.next_cursor ? (
              <Link
                href={`/admin/leads${buildQueryString({
                  ...searchParams,
                  cursor: data.next_cursor,
                })}`}
              >
                <Button variant="ghost">Next page</Button>
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
