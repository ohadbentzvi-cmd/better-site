/**
 * Unsubscribe page — legally required (CAN-SPAM).
 *
 * The email address is passed in the query string from the unsubscribe link
 * in every cold email. Submitting the form posts to the API's /unsubscribe
 * endpoint, which writes the address to the suppression list.
 */
export default function UnsubscribePage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="mb-4 text-2xl font-semibold">Unsubscribe</h1>
        <p className="mb-6 text-neutral-600">
          Enter your email to stop receiving messages from BetterSite.
        </p>
        {/* TODO (Phase 4): form → POST /unsubscribe */}
        <p className="text-sm text-neutral-500">Not yet implemented.</p>
      </div>
    </main>
  );
}
