import { Badge } from "@/components/ui/badge";

interface LeadReviewItem {
  id: string;
  verdict: "approved" | "rejected";
  reason_code: string | null;
  note: string | null;
  analyst_username: string;
  created_at: string;
}

interface ScanReviewItem {
  id: string;
  reasoning: string;
  analyst_username: string;
  created_at: string;
}

interface ReviewHistoryProps {
  leadReviews: LeadReviewItem[];
  scanReviews: ScanReviewItem[];
}

const REASON_LABELS: Record<string, string> = {
  not_icp: "Wrong ICP",
  site_already_good: "Site already good",
  site_broken_or_dead: "Site broken or dead",
  duplicate_or_other: "Duplicate / other",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ReviewHistory({ leadReviews, scanReviews }: ReviewHistoryProps) {
  type Item =
    | { kind: "lead"; ts: number; data: LeadReviewItem }
    | { kind: "scan"; ts: number; data: ScanReviewItem };

  const merged: Item[] = [
    ...leadReviews.map(
      (r): Item => ({ kind: "lead", ts: new Date(r.created_at).getTime(), data: r }),
    ),
    ...scanReviews.map(
      (r): Item => ({ kind: "scan", ts: new Date(r.created_at).getTime(), data: r }),
    ),
  ];
  merged.sort((a, b) => b.ts - a.ts);

  if (!merged.length) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">No reviews yet.</p>
    );
  }

  return (
    <ul className="space-y-4">
      {merged.map((item) => {
        if (item.kind === "lead") {
          const r = item.data;
          return (
            <li key={`l-${r.id}`} className="text-sm">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant={r.verdict === "approved" ? "success" : "danger"}>
                  {r.verdict}
                </Badge>
                {r.reason_code ? (
                  <span className="text-[var(--text-secondary)] text-xs">
                    {REASON_LABELS[r.reason_code] ?? r.reason_code}
                  </span>
                ) : null}
                <span className="text-xs text-[var(--text-tertiary)] ml-auto">
                  {r.analyst_username} · {formatDate(r.created_at)}
                </span>
              </div>
              {r.note ? (
                <p className="text-[var(--text-secondary)] text-sm pl-0.5">
                  {r.note}
                </p>
              ) : null}
            </li>
          );
        }
        const r = item.data;
        return (
          <li key={`s-${r.id}`} className="text-sm">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="neutral">scan feedback</Badge>
              <span className="text-xs text-[var(--text-tertiary)] ml-auto">
                {r.analyst_username} · {formatDate(r.created_at)}
              </span>
            </div>
            <p className="text-[var(--text-secondary)] text-sm">{r.reasoning}</p>
          </li>
        );
      })}
    </ul>
  );
}
