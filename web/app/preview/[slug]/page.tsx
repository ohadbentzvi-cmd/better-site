/**
 * Preview page — the highest-leverage UI surface in the product.
 *
 * Renders the personalized site generated for one lead. Recipients land here
 * from the cold email. Key features (per Phase 4 checklist):
 *   - Before/after slider at top-of-fold
 *   - Mobile-first layout
 *   - Embedded Stripe Elements checkout
 *   - Sticky "Buy this site for $399" CTA bar
 *   - Share-with-partner button
 *
 * Data flow:
 *   1. Server component fetches /preview/:slug from the FastAPI backend
 *   2. Backend returns the extraction + scan + site row
 *   3. All extracted HTML fields have already been sanitized server-side
 *      by the API before we see them here
 *   4. The vertical template component (templates/movers/) renders the
 *      new site using that data
 */

import { notFound } from "next/navigation";

type PreviewPageProps = {
  params: { slug: string };
};

export default async function PreviewPage({ params }: PreviewPageProps) {
  const { slug } = params;

  // TODO (Phase 4):
  // const data = await fetchPreviewData(slug);
  // if (!data) notFound();
  // return <MoversPreview data={data} />;

  if (!slug) notFound();

  return (
    <main className="min-h-screen p-8">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-2 text-2xl font-semibold">Preview: {slug}</h1>
        <p className="text-neutral-500">
          Preview page not yet implemented. This will render the personalized
          site generated for this lead (Phase 4).
        </p>
      </div>
    </main>
  );
}
