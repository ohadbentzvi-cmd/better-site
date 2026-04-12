/**
 * Internal admin dashboard.
 *
 * Behind HTTP basic auth (handled by middleware). Shows:
 *   - Leads table with filters
 *   - Review queue (pending leads with preview iframe + Approve/Reject)
 *   - Cost dashboard (daily spend per external service)
 *   - Pipeline funnel
 *
 * Phase 5 implementation.
 */
export default function AdminPage() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-semibold">BetterSite Admin</h1>
      <p className="mt-2 text-neutral-500">Phase 5 — not yet implemented.</p>
    </main>
  );
}
