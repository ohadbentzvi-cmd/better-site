# DESIGN.md — BetterSite

Design system of record. All UI decisions calibrate against this file. When in doubt, read this before opening Figma or writing Tailwind classes.

> **Scope:** this document currently covers the **Admin Console** (`web/app/admin/*`). Marketing and preview surfaces (`/`, `/preview/[slug]`, `/buy/*`) will receive their own section when built.

---

## North-star principle

**Utility over ornament.** The admin console is a tool, not a brochure. Analysts sit with it for hours labeling leads and scans. Every pixel earns its place by making the next review faster or clearer. If an element doesn't help someone approve, reject, or override a score more confidently, it doesn't belong.

This surface follows the **App UI** rule set (not marketing/landing):
- Calm surface hierarchy, strong typography, few colors
- Dense but readable; minimal chrome
- Utility language (orientation, status, action) — never mood or brand copy
- Cards exist only when the card IS the interaction

---

## Typography

- **Primary typeface:** [Inter](https://rsms.me/inter/). Wired via `next/font/google` with `variable` + `display: swap`. No fallback to system stacks in production.
- **Monospace:** JetBrains Mono, used only for domains, UUIDs, raw metric values.
- **Scale (rem on 16px root):**

  | Token       | Size      | Use                           |
  |-------------|-----------|-------------------------------|
  | `text-xs`   | 12px / 16 | metadata, table cell labels   |
  | `text-sm`   | 14px / 20 | body, table cells, buttons    |
  | `text-base` | 16px / 24 | form inputs, default paragraph|
  | `text-lg`   | 18px / 28 | section headings              |
  | `text-xl`   | 24px / 32 | page titles                   |
  | `text-2xl`  | 32px / 40 | reserved — not used on admin  |

- **Weights:** 400 (body), 500 (UI labels, table headers), 600 (headings, emphasis). Never 700+, never italic.
- **Numerics:** add `font-variant-numeric: tabular-nums` to every cell that displays a score, count, timestamp, or metric. Scores must not jitter between rows.

---

## Color

Neutrals do the work. Accents are reserved for meaning, never decoration.

```css
/* web/app/globals.css — extend existing :root */
:root {
  /* surfaces */
  --surface-0: #ffffff;   /* page bg */
  --surface-1: #fafafa;   /* sidebar, subtle panels */
  --surface-2: #f4f4f5;   /* table header, hover */
  --surface-3: #e4e4e7;   /* borders, dividers */

  /* text */
  --text-primary:   #0a0a0a;
  --text-secondary: #525252;
  --text-tertiary:  #a3a3a3;  /* metadata only */
  --text-inverse:   #ffffff;

  /* semantic — used by status, not decoration */
  --accent:         #2563eb;  /* blue-600 — primary actions */
  --accent-hover:   #1d4ed8;
  --success:        #15803d;  /* green-700 — approved verdict */
  --success-soft:   #dcfce7;  /* badge bg */
  --danger:         #b91c1c;  /* red-700 — rejected verdict, errors */
  --danger-soft:    #fee2e2;
  --warning:        #a16207;  /* amber-700 — partial scan, stale */
  --warning-soft:   #fef3c7;

  /* focus */
  --focus-ring: #2563eb;
}
```

**Rules:**
- No purple, violet, indigo gradients. Ever. Flat colors only.
- Background is always `--surface-0`. Panels and sidebar use `--surface-1`. Hover rows use `--surface-2`.
- Status colors are used only in `<Badge>` and inline icons, never as card backgrounds.
- Contrast: body text on `--surface-0` ≥ WCAG AA (4.5:1). `--text-tertiary` only on text ≥ `text-sm` and only for secondary metadata.

---

## Spacing

4-based scale. Tailwind defaults already align.

```
  1 = 4px       4 = 16px      8 = 32px
  2 = 8px       5 = 20px      10 = 40px
  3 = 12px      6 = 24px      12 = 48px
```

- Page gutter: `px-6` (24px). No centered container. Full-bleed content with fixed sidebar.
- Table row vertical padding: `py-2.5` (10px). Tight but not cramped.
- Form field vertical rhythm: `space-y-4` (16px between label groups), `space-y-1.5` within a group (label → input).

---

## Layout

```
┌────────────┬─────────────────────────────────────────────┐
│            │  PageHeader (title + secondary action)      │
│  Sidebar   │  ─────────────────────────────────────────  │
│  (fixed    │                                             │
│   220px)   │  Page content (scroll)                      │
│            │                                             │
└────────────┴─────────────────────────────────────────────┘
```

- **Sidebar:** fixed width 220px, `bg-[var(--surface-1)]`, right border `1px solid var(--surface-3)`. Vertical list of destinations (Leads). Bottom-anchored analyst identity + Logout.
- **Content:** flush to sidebar, no max-width. The table and detail views breathe to the full viewport width so wide-screen analysts see more columns / more scan data without scrolling.
- **Mobile:** admin is **desktop-only** in v1. Below 1024px, show a "This tool is designed for desktop" message and stop. Do not attempt responsive. (Rationale: analysts review from desks, not phones; responsive is wasted work here.)

---

## Components (reusable vocabulary)

These live under `web/components/ui/*.tsx`. **No shadcn/ui** per the eng review — keep deps minimal. Plain React + Tailwind.

### Primitives

| Component       | File                          | Purpose                                         |
|-----------------|-------------------------------|-------------------------------------------------|
| `<Button>`      | `ui/button.tsx`               | Variants: `primary`, `ghost`, `danger`          |
| `<Input>`       | `ui/input.tsx`                | Text + email types, consistent focus ring       |
| `<Textarea>`    | `ui/textarea.tsx`             | Multi-line for notes + reasoning                |
| `<Select>`      | `ui/select.tsx`               | Native `<select>` styled to match inputs        |
| `<Badge>`       | `ui/badge.tsx`                | Status pill. Variants: `neutral`, `success`, `danger`, `warning` |
| `<Label>`       | `ui/label.tsx`                | Form label, `text-sm font-medium`               |
| `<Field>`       | `ui/field.tsx`                | Wraps Label + control + error slot              |
| `<Divider>`     | `ui/divider.tsx`              | 1px `bg-[var(--surface-3)]`                     |

### Layout

| Component       | File                          | Purpose                                         |
|-----------------|-------------------------------|-------------------------------------------------|
| `<PageHeader>`  | `ui/page-header.tsx`          | Title (text-xl font-semibold) + optional action |
| `<Card>`        | `ui/card.tsx`                 | Panel with `border border-[var(--surface-3)] rounded-md bg-white`. Used for detail sections only, NOT in lists. |
| `<EmptyState>`  | `ui/empty-state.tsx`          | Icon + title + 1-line context + primary action  |
| `<Spinner>`     | `ui/spinner.tsx`              | 16px animated ring, used in buttons + inline    |

### Domain components (admin-specific)

| Component          | File                                       | Purpose                                       |
|--------------------|--------------------------------------------|-----------------------------------------------|
| `<LeadsTable>`     | `admin/components/leads-table.tsx`         | Virtualized once row count > 200 (not v1)     |
| `<FilterBar>`      | `admin/components/filter-bar.tsx`          | Status/vertical/score/email/reviewed filters + search |
| `<ScoreBar>`       | `admin/components/score-bar.tsx`           | Horizontal bar 0–100 with tick at 60 (pass/fail) + numeric value. Partial scans render as striped pattern with "—" value. |
| `<DimensionScores>`| `admin/components/dimension-scores.tsx`    | Perf/SEO/AI/Security mini-bars stacked       |
| `<IssueList>`      | `admin/components/issue-list.tsx`          | Renders `issues_json` — icon per severity, title, optional detail toggle |
| `<MetricsGrid>`    | `admin/components/metrics-grid.tsx`        | 2×3 grid of curated raw metrics (LCP, CLS, TBT, FCP, TTFB, page weight) with units + thresholds |
| `<ReviewForm>`     | `admin/components/review-form.tsx`         | Approve/Reject radio + reason select + note textarea |
| `<ScanFeedbackForm>`| `admin/components/scan-feedback-form.tsx` | Single textarea + submit                      |
| `<EmailBackfillForm>`| `admin/components/email-backfill-form.tsx`| Shown inline when `email IS NULL`            |
| `<ReviewHistory>`  | `admin/components/review-history.tsx`      | Chronological list of prior lead_reviews + scan_reviews |

### Component specs (the ones with real decisions)

**`<Button>`**
- `primary`: `bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] focus-visible:ring-2 ring-[var(--focus-ring)] ring-offset-2 px-3 py-1.5 text-sm font-medium rounded-md`
- `ghost`: `bg-transparent text-[var(--text-primary)] hover:bg-[var(--surface-2)] px-3 py-1.5 text-sm font-medium rounded-md`
- `danger`: same as primary but `bg-[var(--danger)] hover:bg-red-800`
- Loading state: swap label for `<Spinner />` + "Working...". Disable button. No layout shift.
- Keyboard: Enter/Space triggers. Visible focus ring always.
- Touch target: min 36px height (buttons are desktop primary; tighter than mobile 44px is acceptable here).

**`<Badge>`**
- All variants: `inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium`
- `neutral`: `bg-[var(--surface-2)] text-[var(--text-secondary)]` — default for LeadStatus values like `new`, `scanned`
- `success`: `bg-[var(--success-soft)] text-[var(--success)]` — `approved`
- `danger`: `bg-[var(--danger-soft)] text-[var(--danger)]` — `rejected`, `bounced`
- `warning`: `bg-[var(--warning-soft)] text-[var(--warning)]` — `scan_partial=true` indicator

**`<ScoreBar>`**
```
  Full scan, score 72:
  ████████████████████████████████████▏                72
  ──────────────────────────▲─── pass line at 60

  Partial scan:
  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                —  partial
```
- 200px wide, 6px tall, `rounded-full`
- Fill color based on score band: 0–39 `--danger`, 40–59 `--warning`, 60+ `--success`
- Tick mark at 60 (pass/fail line) in `--text-tertiary`
- Partial scans: striped pattern (CSS `repeating-linear-gradient`) + `—` instead of number + `partial` badge on the right
- `tabular-nums` on the numeric

**`<EmptyState>`** — empty states are features per our design principles
- Used for: zero filter results, unreviewed queue empty, lead detail with no scan yet
- Structure: small icon (24px, `--text-tertiary`) → title (`text-base font-medium`) → 1 line of context (`text-sm text-[var(--text-secondary)]`) → optional primary action
- Examples:
  - "No leads match these filters." / "Clear filters to see all 1,203 leads." / [Clear filters] button
  - "This lead hasn't been scanned yet." / "Scans run automatically. Check back in a few minutes." / no action
  - "No reviews yet." / "Be the first to weigh in." / review form is right below, no need for a button here

---

## Interaction states (complete matrix)

Every screen must specify all six states. Placeholders in the plan will be replaced with links back to this table.

| Screen            | Loading                              | Empty                              | Error                                          | Success                         | Partial                          | First-time                       |
|-------------------|--------------------------------------|------------------------------------|------------------------------------------------|---------------------------------|----------------------------------|----------------------------------|
| Login             | Button spinner + "Signing in..."     | n/a                                | Inline error under form, input highlights red  | Redirect to `/admin/leads`      | n/a                              | Same as empty                    |
| Leads list        | Skeleton rows (8 shimmer rows)       | `<EmptyState>`                     | Top banner: "Couldn't load leads. [Retry]"     | Table renders                   | Show leads w/ partial scans w/ warning badge | Show all leads, no filter preset |
| Lead detail       | Skeleton cards for each panel        | Lead-not-found → 404 page w/ link back | Banner "Couldn't load this lead. [Retry]" | All panels filled               | Scan section shows `<Badge warning>Partial scan</Badge>` | n/a                              |
| Review form       | Button spinner during submit         | n/a                                | Field-level errors from 422; top-level toast for 5xx | Green toast "Review saved" + history updates | n/a                              | n/a                              |
| Email backfill    | Button spinner                       | n/a                                | 409 → inline "Email already set for this lead" | Form collapses to "Email: foo@bar.com (manual)" | n/a                              | Visible only when email is null  |
| Scan feedback     | Button spinner                       | n/a                                | Same as review form                            | Toast + form resets             | n/a                              | Form hidden if no scan exists    |

**Rules:**
- Skeleton shimmer uses `--surface-2` and `--surface-3` at 600ms cycle.
- Toasts auto-dismiss at 4s, top-right, stack max 3, keyboard-dismissible.
- Errors never swallow — every 5xx gets a visible banner with retry.

---

## Copy voice

Utility language. No exclamation marks. No "Oops" or "Uh oh". No "Awesome!". No emojis.

| Context            | Good                                      | Bad                                        |
|--------------------|-------------------------------------------|--------------------------------------------|
| Login CTA          | Sign in                                   | Let's go!                                  |
| Empty table        | No leads match these filters.             | Uh oh, nothing to see here!                |
| Submit success     | Review saved                              | Awesome! Your review has been submitted 🎉 |
| 5xx error          | Something failed on our end. Retry?       | Oops! Something went wrong :(              |
| Reject reason      | Wrong ICP (vertical / geo / size)         | Not our type of customer                   |

Button labels are verbs: **Sign in**, **Approve**, **Reject**, **Submit feedback**, **Add email**, **Clear filters**, **Log out**.

---

## Accessibility

- All interactive elements reachable via Tab. Never `tabindex > 0`.
- Visible focus ring on all focusable elements. No `outline: none` without a replacement.
- All form fields have `<label for>` or wrapping `<label>`. Never placeholder-as-label.
- Color is never the sole carrier of meaning. Approved/Rejected badges use color AND the word.
- Target sizes: 36px minimum for buttons, 44px not enforced (desktop-primary).
- Semantic HTML: `<main>`, `<nav>`, `<header>`, proper heading order (h1 per page, h2 for sections).
- Tables: `<th scope="col">`, `<caption class="sr-only">` describing the table.
- ARIA: `aria-busy` on loading regions, `aria-live="polite"` on toast region, `aria-current="page"` on active sidebar link.

---

## Motion

- Transitions: `transition-colors duration-150` on hover states. Nothing else.
- No page transitions. No scroll animations. No parallax. No skeletons that "grow in."
- The `<Spinner>` is the only continuous motion. Shimmer loops on skeletons only while data is loading.
- `prefers-reduced-motion: reduce` → disable shimmer + spinner animation (show static indicator instead).

---

## What this DESIGN.md does NOT cover

- Marketing / preview / buy pages. Those are a different aesthetic surface (conversion-driven, brand-forward) and will be added to this file when built.
- Mobile/tablet layouts for admin. Desktop-only in v1.
- Dark mode. Not in scope; can add via CSS variable swap later without breaking anything above.
- Illustrations. No illustration system; icons only ([Lucide](https://lucide.dev/) via `lucide-react`, 16–20px default).
