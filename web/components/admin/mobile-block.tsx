/**
 * Desktop-only gate. Renders full-screen text at viewports below 1024px.
 * Per DESIGN.md: admin is not a mobile experience and won't become one in v1.
 */
export function MobileBlock() {
  return (
    <div className="fixed inset-0 z-50 bg-[var(--surface-0)] flex items-center justify-center p-8 lg:hidden">
      <div className="max-w-sm text-center">
        <div className="text-base font-medium text-[var(--text-primary)] mb-2">
          Open on a desktop.
        </div>
        <p className="text-sm text-[var(--text-secondary)]">
          This tool is designed for wide screens. Analyst workflows need the space.
        </p>
      </div>
    </div>
  );
}
