/**
 * Minimal brand landing page.
 *
 * POC scope: this page is only visible if someone types bettersite.co
 * directly. The actual product surface is /preview/[slug] (personalized
 * preview pages reached from cold email).
 *
 * Intentionally NOT a product page — no public self-serve flow in POC.
 */
export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-xl text-center">
        <h1 className="mb-4 text-4xl font-semibold">BetterSite</h1>
        <p className="text-lg text-neutral-600">
          A web studio that builds better websites for small businesses.
        </p>
      </div>
    </main>
  );
}
