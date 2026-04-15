interface ScoreBarProps {
  score: number | null;
  partial: boolean;
  width?: number;
}

export function ScoreBar({ score, partial, width = 160 }: ScoreBarProps) {
  if (partial || score === null) {
    return (
      <div className="flex items-center gap-2">
        <div
          aria-label="Partial scan, no overall score"
          className="h-1.5 rounded-full bg-[var(--surface-3)] relative overflow-hidden"
          style={{
            width,
            backgroundImage:
              "repeating-linear-gradient(135deg, var(--surface-2) 0, var(--surface-2) 4px, var(--surface-3) 4px, var(--surface-3) 8px)",
          }}
        />
        <span className="text-xs text-[var(--text-tertiary)] tabular-nums">
          — partial
        </span>
      </div>
    );
  }

  const clamped = Math.max(0, Math.min(100, score));
  const color =
    clamped < 40
      ? "var(--danger)"
      : clamped < 60
        ? "var(--warning)"
        : "var(--success)";

  return (
    <div className="flex items-center gap-2">
      <div
        className="relative h-1.5 rounded-full bg-[var(--surface-2)]"
        style={{ width }}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
      >
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all"
          style={{ width: `${clamped}%`, background: color }}
        />
        {/* Pass/fail tick at 60 */}
        <div
          aria-hidden="true"
          className="absolute top-[-2px] w-px h-[10px] bg-[var(--text-tertiary)]"
          style={{ left: "60%" }}
        />
      </div>
      <span className="text-sm font-medium tabular-nums text-[var(--text-primary)] w-8 text-right">
        {clamped}
      </span>
    </div>
  );
}
