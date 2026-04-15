"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { submitReviewAction } from "@/app/admin/actions";

const REASON_LABELS: Record<string, string> = {
  not_icp: "Wrong ICP (vertical / geo / size)",
  site_already_good: "Site is already good",
  site_broken_or_dead: "Site is broken or dead",
  duplicate_or_other: "Duplicate or other (requires note)",
};

interface ReviewFormProps {
  leadId: string;
}

export function ReviewForm({ leadId }: ReviewFormProps) {
  const [verdict, setVerdict] = useState<"approved" | "rejected" | null>(null);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const needsNote = verdict === "rejected" && reason === "duplicate_or_other";
  const valid =
    verdict === "approved" ||
    (verdict === "rejected" && reason && (!needsNote || note.trim().length > 0));

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || !verdict) return;
    setError(null);

    const payload = {
      leadId,
      verdict,
      reason_code: verdict === "rejected" ? reason : null,
      note: note.trim() || null,
    };

    startTransition(async () => {
      const result = await submitReviewAction(payload);
      if (result?.error) {
        setError(result.error);
        return;
      }
      // Reset
      setVerdict(null);
      setReason("");
      setNote("");
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-[var(--text-primary)] mb-2">
          Verdict
        </legend>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="radio"
            name="verdict"
            value="approved"
            checked={verdict === "approved"}
            onChange={() => {
              setVerdict("approved");
              setReason("");
            }}
          />
          Approve
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="radio"
            name="verdict"
            value="rejected"
            checked={verdict === "rejected"}
            onChange={() => setVerdict("rejected")}
          />
          Reject
        </label>
      </fieldset>

      {verdict === "rejected" ? (
        <Field label="Reason" htmlFor="review-reason">
          <Select
            id="review-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
          >
            <option value="">Select a reason...</option>
            {Object.entries(REASON_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}

      <Field
        label="Note"
        htmlFor="review-note"
        hint={needsNote ? "Required — explain why this is duplicate or other" : "Optional context"}
      >
        <Textarea
          id="review-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={needsNote ? "Explain..." : ""}
          invalid={needsNote && note.trim().length === 0 && error !== null}
        />
      </Field>

      {error ? (
        <p className="text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}

      <Button type="submit" disabled={!valid} loading={pending}>
        Submit review
      </Button>
    </form>
  );
}
