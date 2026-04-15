interface DimensionScoresProps {
  performance: number | null;
  seo: number | null;
  aiReadiness: number | null;
  security: number | null;
}

const DIMS: { key: keyof DimensionScoresProps; label: string }[] = [
  { key: "performance", label: "Performance" },
  { key: "seo", label: "SEO" },
  { key: "aiReadiness", label: "AI readiness" },
  { key: "security", label: "Security" },
];

function color(v: number | null): string {
  if (v === null) return "var(--surface-3)";
  if (v < 40) return "var(--danger)";
  if (v < 60) return "var(--warning)";
  return "var(--success)";
}

export function DimensionScores(props: DimensionScoresProps) {
  return (
    <div className="grid grid-cols-1 gap-y-2">
      {DIMS.map((d) => {
        const value = props[d.key];
        const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
        return (
          <div key={d.key} className="flex items-center gap-3">
            <div className="w-28 text-xs text-[var(--text-secondary)] shrink-0">
              {d.label}
            </div>
            <div className="flex-1 h-1 rounded-full bg-[var(--surface-2)] relative">
              <div
                className="absolute left-0 top-0 h-full rounded-full"
                style={{ width: `${pct}%`, background: color(value) }}
              />
            </div>
            <div className="w-10 text-right text-sm font-medium tabular-nums text-[var(--text-primary)]">
              {value === null ? "—" : value}
            </div>
          </div>
        );
      })}
    </div>
  );
}
