export function Divider({ className }: { className?: string }) {
  return (
    <div
      className={`h-px w-full bg-[var(--surface-3)] ${className ?? ""}`}
      role="separator"
    />
  );
}
