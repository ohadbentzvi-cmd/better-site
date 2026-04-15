interface MetricsGridProps {
  metrics: Record<string, unknown>;
}

interface MetricSpec {
  key: string;
  label: string;
  format: (v: unknown) => string;
}

const METRICS: MetricSpec[] = [
  {
    key: "lcp_ms",
    label: "LCP",
    format: (v) => (typeof v === "number" ? `${(v / 1000).toFixed(2)}s` : "—"),
  },
  {
    key: "cls",
    label: "CLS",
    format: (v) => (typeof v === "number" ? v.toFixed(3) : "—"),
  },
  {
    key: "tbt_ms",
    label: "TBT",
    format: (v) => (typeof v === "number" ? `${Math.round(v)}ms` : "—"),
  },
  {
    key: "fcp_ms",
    label: "FCP",
    format: (v) => (typeof v === "number" ? `${(v / 1000).toFixed(2)}s` : "—"),
  },
  {
    key: "ttfb_ms",
    label: "TTFB",
    format: (v) => (typeof v === "number" ? `${Math.round(v)}ms` : "—"),
  },
  {
    key: "page_weight_kb",
    label: "Page weight",
    format: (v) => (typeof v === "number" ? `${Math.round(v)} KB` : "—"),
  },
];

export function MetricsGrid({ metrics }: MetricsGridProps) {
  return (
    <div className="grid grid-cols-3 gap-px bg-[var(--surface-3)] rounded-md overflow-hidden border border-[var(--surface-3)]">
      {METRICS.map((m) => (
        <div key={m.key} className="bg-white px-3 py-2.5">
          <div className="text-xs text-[var(--text-secondary)]">{m.label}</div>
          <div className="text-sm font-medium tabular-nums text-[var(--text-primary)] mt-0.5">
            {m.format(metrics[m.key])}
          </div>
        </div>
      ))}
    </div>
  );
}
