"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { changePasswordAction } from "@/app/admin/actions";

export function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!currentPassword || !newPassword) return;
    setError(null);
    setSuccess(null);

    startTransition(async () => {
      const result = await changePasswordAction({ currentPassword, newPassword });
      if (result?.error) {
        setError(result.error);
        return;
      }
      setSuccess("Password changed.");
      setCurrentPassword("");
      setNewPassword("");
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
      <Field label="Current password" htmlFor="current-password">
        <Input
          id="current-password"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
          autoComplete="current-password"
        />
      </Field>
      <Field label="New password" htmlFor="new-password-change" hint="At least 8 characters">
        <Input
          id="new-password-change"
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
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
      <Button type="submit" variant="ghost" disabled={!currentPassword || newPassword.length < 8} loading={pending}>
        Change password
      </Button>
    </form>
  );
}
