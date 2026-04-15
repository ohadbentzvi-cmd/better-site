"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { submitEmailBackfillAction } from "@/app/admin/actions";

interface EmailBackfillFormProps {
  leadId: string;
}

export function EmailBackfillForm({ leadId }: EmailBackfillFormProps) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setError(null);
    startTransition(async () => {
      const result = await submitEmailBackfillAction({ leadId, email });
      if (result?.error) {
        setError(result.error);
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Field label="Email" htmlFor="email-backfill" error={error}>
        <div className="flex gap-2">
          <Input
            id="email-backfill"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@example.com"
            invalid={!!error}
            required
          />
          <Button type="submit" disabled={!email} loading={pending}>
            Add email
          </Button>
        </div>
      </Field>
    </form>
  );
}
