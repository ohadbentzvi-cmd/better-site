"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { createAnalystAction } from "@/app/admin/actions";

export function CreateAnalystForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) return;
    setError(null);
    setSuccess(null);

    startTransition(async () => {
      const result = await createAnalystAction({ username, password });
      if (result?.error) {
        setError(result.error);
        return;
      }
      setSuccess(`Analyst "${username}" created. They can now sign in.`);
      setUsername("");
      setPassword("");
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
      <Field label="Username" htmlFor="new-username" hint="Letters, numbers, dashes, underscores, dots">
        <Input
          id="new-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          pattern="^[a-zA-Z0-9_.\-]+$"
          required
          autoComplete="off"
        />
      </Field>
      <Field label="Password" htmlFor="new-password" hint="At least 8 characters">
        <Input
          id="new-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
          autoComplete="new-password"
        />
      </Field>
      {error ? (
        <p className="text-sm text-[var(--danger)]" role="alert">{error}</p>
      ) : null}
      {success ? (
        <p className="text-sm text-[var(--success)]" role="status">{success}</p>
      ) : null}
      <Button type="submit" disabled={!username || password.length < 8} loading={pending}>
        Create analyst
      </Button>
    </form>
  );
}
