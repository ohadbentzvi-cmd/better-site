"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { submitScanFeedbackAction } from "@/app/admin/actions";

interface ScanFeedbackFormProps {
  scanId: string;
}

export function ScanFeedbackForm({ scanId }: ScanFeedbackFormProps) {
  const [reasoning, setReasoning] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (reasoning.trim().length === 0) return;
    setError(null);
    startTransition(async () => {
      const result = await submitScanFeedbackAction({ scanId, reasoning });
      if (result?.error) {
        setError(result.error);
        return;
      }
      setReasoning("");
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Field
        label="Scan feedback"
        htmlFor="scan-feedback"
        hint="Why is this scan's score wrong? Free text."
      >
        <Textarea
          id="scan-feedback"
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
          placeholder="e.g. This site should score lower because the layout is broken on mobile..."
          rows={3}
        />
      </Field>
      {error ? (
        <p className="text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button
        type="submit"
        variant="ghost"
        disabled={reasoning.trim().length === 0}
        loading={pending}
      >
        Submit feedback
      </Button>
    </form>
  );
}
