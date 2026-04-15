import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScoreBar } from "./score-bar";

interface LeadRow {
  id: string;
  business_name: string;
  canonical_domain: string;
  website_url: string;
  vertical: string;
  status: string;
  email: string | null;
  email_source: string | null;
  scan: {
    score: number | null;
    scan_partial: boolean;
  } | null;
  latest_review: {
    verdict: "approved" | "rejected";
    analyst_username: string;
    created_at: string;
  } | null;
}

interface LeadsTableProps {
  rows: LeadRow[];
}

/** Defense-in-depth: reject non-http(s) URLs before rendering into href. */
function isSafeHttpUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function relativeDays(iso: string): string {
  const d = (Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24);
  if (d < 1) return "today";
  if (d < 2) return "1d";
  return `${Math.floor(d)}d`;
}

export function LeadsTable({ rows }: LeadsTableProps) {
  return (
    <div className="border-t border-[var(--surface-3)]">
      <table className="w-full text-sm">
        <caption className="sr-only">Leads</caption>
        <thead className="bg-[var(--surface-1)] text-[var(--text-secondary)]">
          <tr>
            <th scope="col" className="text-left font-medium px-4 py-2">
              Business
            </th>
            <th scope="col" className="text-left font-medium px-4 py-2">
              Domain
            </th>
            <th scope="col" className="text-left font-medium px-4 py-2">
              Vertical
            </th>
            <th scope="col" className="text-left font-medium px-4 py-2">
              Score
            </th>
            <th scope="col" className="text-left font-medium px-4 py-2">
              Status
            </th>
            <th scope="col" className="text-left font-medium px-4 py-2">
              Last reviewed
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className="border-t border-[var(--surface-3)] hover:bg-[var(--surface-2)] transition-colors"
            >
              <td className="px-4 py-2.5">
                <Link
                  href={`/admin/leads/${row.id}`}
                  className="font-medium text-[var(--text-primary)] hover:underline"
                >
                  {row.business_name}
                </Link>
              </td>
              <td className="px-4 py-2.5 font-[var(--font-mono),ui-monospace] text-xs">
                {isSafeHttpUrl(row.website_url) ? (
                  <a
                    href={row.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[var(--text-secondary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {row.canonical_domain}
                    <ExternalLink size={12} aria-hidden="true" className="opacity-60" />
                  </a>
                ) : (
                  <span className="text-[var(--text-secondary)]">
                    {row.canonical_domain}
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                {row.vertical}
              </td>
              <td className="px-4 py-2.5">
                {row.scan ? (
                  <ScoreBar
                    score={row.scan.score}
                    partial={row.scan.scan_partial}
                    width={120}
                  />
                ) : (
                  <span className="text-xs text-[var(--text-tertiary)]">
                    not scanned
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5">
                <Badge variant="neutral">{row.status}</Badge>
              </td>
              <td className="px-4 py-2.5 text-xs text-[var(--text-tertiary)]">
                {row.latest_review ? (
                  <>
                    {row.latest_review.analyst_username} ·{" "}
                    {relativeDays(row.latest_review.created_at)}
                  </>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
