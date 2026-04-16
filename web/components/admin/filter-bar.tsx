"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";

// Matches the LeadStatus enum in pipeline/models/lead.py.
const STATUSES = [
  "new",
  "scanned",
  "extracted",
  "built",
  "review_pending",
  "approved",
  "rejected",
  "emailed",
] as const;

export function FilterBar() {
  const router = useRouter();
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();

  function applyFilter(partial: Record<string, string | null>) {
    const params = new URLSearchParams(sp.toString());
    for (const [k, v] of Object.entries(partial)) {
      if (v === null || v === "") params.delete(k);
      else params.set(k, v);
    }
    params.delete("cursor");
    startTransition(() => {
      router.push(`/admin/leads?${params.toString()}`);
    });
  }

  function clearAll() {
    startTransition(() => router.push("/admin/leads"));
  }

  function handleSearchSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    applyFilter({ q: (fd.get("q") as string) || null });
  }

  return (
    <form
      onSubmit={handleSearchSubmit}
      className="flex flex-wrap items-center gap-2 py-3"
      role="search"
    >
      <Input
        name="q"
        defaultValue={sp.get("q") ?? ""}
        placeholder="Search business or domain..."
        className="max-w-[280px]"
      />
      <Select
        defaultValue={sp.get("status") ?? ""}
        onChange={(e) => applyFilter({ status: e.target.value || null })}
        aria-label="Filter by status"
      >
        <option value="">All statuses</option>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </Select>
      <Select
        defaultValue={sp.get("reviewed") ?? ""}
        onChange={(e) => applyFilter({ reviewed: e.target.value || null })}
        aria-label="Filter by reviewed status"
      >
        <option value="">Reviewed: any</option>
        <option value="false">Unreviewed</option>
        <option value="true">Reviewed</option>
      </Select>
      <Select
        defaultValue={sp.get("has_email") ?? ""}
        onChange={(e) => applyFilter({ has_email: e.target.value || null })}
        aria-label="Filter by email presence"
      >
        <option value="">Email: any</option>
        <option value="true">Has email</option>
        <option value="false">No email</option>
      </Select>
      <Select
        defaultValue={activeScoreKey(sp)}
        onChange={(e) => {
          const v = e.target.value;
          if (!v) applyFilter({ score_min: null, score_max: null });
          else if (v.startsWith("min:"))
            applyFilter({ score_min: v.slice(4), score_max: null });
          else if (v.startsWith("max:"))
            applyFilter({ score_min: null, score_max: v.slice(4) });
        }}
        aria-label="Score filter"
      >
        <option value="">Score: any</option>
        <option value="min:80">≥ 80</option>
        <option value="min:60">≥ 60 (pass)</option>
        <option value="min:40">≥ 40</option>
        <option value="max:60">≤ 60 (below pass)</option>
        <option value="max:40">≤ 40</option>
        <option value="max:20">≤ 20</option>
      </Select>
      <Button type="submit" variant="ghost" loading={pending}>
        Apply
      </Button>
      {hasActiveFilter(sp) ? (
        <Button type="button" variant="ghost" onClick={clearAll}>
          Clear filters
        </Button>
      ) : null}
    </form>
  );
}

/** Cursor is pagination state, not a filter. Don't count it as active. */
function hasActiveFilter(sp: URLSearchParams): boolean {
  for (const key of sp.keys()) {
    if (key !== "cursor") return true;
  }
  return false;
}

/** Derive the <select> value from the current search params. */
function activeScoreKey(sp: URLSearchParams): string {
  const min = sp.get("score_min");
  const max = sp.get("score_max");
  if (min) return `min:${min}`;
  if (max) return `max:${max}`;
  return "";
}
