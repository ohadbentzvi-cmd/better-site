/**
 * Movers vertical template — v0.
 *
 * Mobile-first. Every field in content is optional; every visual element
 * must degrade gracefully when its input is missing (text wordmark when no
 * logo, stock hero when no hero image, template default colors when no
 * brand colors).
 *
 * Phase 3 implementation: this is a placeholder. The real template layout
 * will be designed before the first real batch.
 */

export type MoversContent = {
  business_name?: string;
  tagline?: string;
  about?: string;
  services?: string[];
  phone?: string;
  email?: string;
  address?: string;
  social_links?: Record<string, string>;
  logo_url?: string;
  hero_url?: string;
  brand_colors?: string[];
};

type Props = {
  content: MoversContent;
};

export default function MoversTemplate({ content }: Props) {
  const name = content.business_name ?? "Your Moving Company";

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b p-6">
        <h1 className="text-2xl font-bold">{name}</h1>
        {content.tagline && (
          <p className="mt-1 text-neutral-600">{content.tagline}</p>
        )}
      </header>
      <main className="p-6">
        <p className="text-neutral-500">
          Movers template placeholder — Phase 3.
        </p>
      </main>
    </div>
  );
}
