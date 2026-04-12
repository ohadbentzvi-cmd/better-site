/**
 * Post-payment success page.
 *
 * The customer lands here from Stripe Elements after a successful checkout.
 * Shows the next-steps DNS guide (v0 is manual; post-POC may automate).
 */
export default function BuySuccessPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-2xl text-center">
        <h1 className="mb-4 text-3xl font-semibold">Thanks — your site is yours.</h1>
        <p className="mb-6 text-neutral-600">
          We&apos;ll be in touch in the next 24 hours with instructions for pointing
          your domain at your new site. Nothing you need to do right now.
        </p>
        <p className="text-sm text-neutral-500">
          Questions? Reply to your confirmation email or write to hello@bettersite.co.
        </p>
      </div>
    </main>
  );
}
