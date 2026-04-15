"use client";

import { useFormState, useFormStatus } from "react-dom";
import { useSearchParams } from "next/navigation";
import { loginAction } from "@/app/admin/actions";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

type LoginState = { error?: string } | null;

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" loading={pending} className="w-full">
      Sign in
    </Button>
  );
}

export default function LoginPage() {
  const [state, action] = useFormState<LoginState, FormData>(
    loginAction as (prev: LoginState, fd: FormData) => Promise<LoginState>,
    null,
  );
  const sp = useSearchParams();
  const next = sp?.get("next") ?? "/admin/leads";

  return (
    <div className="min-h-screen bg-[var(--surface-1)] flex items-center justify-center px-4">
      <form
        action={action}
        className="w-full max-w-sm bg-white border border-[var(--surface-3)] rounded-lg p-6 space-y-5"
      >
        <div>
          <div className="text-lg font-semibold text-[var(--text-primary)]">
            Sign in
          </div>
          <div className="text-sm text-[var(--text-secondary)] mt-0.5">
            BetterSite Admin
          </div>
        </div>

        <input type="hidden" name="next" value={next} />

        <Field label="Username" htmlFor="username">
          <Input
            id="username"
            name="username"
            autoComplete="username"
            required
            autoFocus
            invalid={!!state?.error}
          />
        </Field>

        <Field label="Password" htmlFor="password">
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            invalid={!!state?.error}
          />
        </Field>

        {state?.error ? (
          <p className="text-sm text-[var(--danger)]" role="alert">
            {state.error}
          </p>
        ) : null}

        <SubmitButton />
      </form>
    </div>
  );
}
