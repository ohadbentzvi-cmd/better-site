"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { apiFetch, ApiError } from "@/lib/admin/api";
import {
  SESSION_COOKIE_NAME,
  SESSION_MAX_AGE,
  signSession,
  verifySession,
  type AdminSession,
} from "@/lib/admin/session";

async function currentSession(): Promise<AdminSession | null> {
  const token = cookies().get(SESSION_COOKIE_NAME)?.value;
  if (!token) return null;
  return verifySession(token);
}

// ── Login ────────────────────────────────────────────────────────────────
export async function loginAction(_prev: unknown, formData: FormData) {
  const username = String(formData.get("username") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const next = String(formData.get("next") ?? "/admin/leads");

  if (!username || !password) {
    return { error: "Enter a username and password." };
  }

  try {
    const resp = await apiFetch<{
      analyst_id: string;
      username: string;
      is_superadmin: boolean;
    }>("/admin/auth/verify", { method: "POST", body: { username, password } });

    const token = await signSession({
      analyst_id: resp.analyst_id,
      username: resp.username,
      is_superadmin: resp.is_superadmin,
    });
    cookies().set(SESSION_COOKIE_NAME, token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: SESSION_MAX_AGE,
    });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 429) {
        return { error: "Too many attempts. Wait 15 minutes." };
      }
      if (err.status === 401) {
        return { error: "Username or password is incorrect." };
      }
    }
    return { error: "Something failed on our end. Try again." };
  }

  redirect(safeNext(next));
}

/** Defense against open-redirects via the `next` form field.
 *
 * Reject anything that isn't a plain path under /admin/. Blocks near-miss
 * patterns like /admin@evil.com and absolute URLs sneaking through. */
function safeNext(next: string): string {
  const DEFAULT = "/admin/leads";
  if (!next.startsWith("/admin/")) return DEFAULT;
  if (next.includes("//") || next.includes("@") || next.includes(":")) return DEFAULT;
  return next;
}

export async function logoutAction() {
  cookies().delete(SESSION_COOKIE_NAME);
  redirect("/admin/login");
}

// ── Review submission ───────────────────────────────────────────────────
interface SubmitReviewPayload {
  leadId: string;
  verdict: "approved" | "rejected";
  reason_code: string | null;
  note: string | null;
}

export async function submitReviewAction(payload: SubmitReviewPayload) {
  const session = await currentSession();
  if (!session) return { error: "Session expired. Reload the page." };

  try {
    await apiFetch(`/admin/leads/${payload.leadId}/review`, {
      method: "POST",
      session,
      body: {
        verdict: payload.verdict,
        reason_code: payload.reason_code,
        note: payload.note,
      },
    });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 422) {
        return { error: "Check the required fields and try again." };
      }
      if (err.status === 404) {
        return { error: "Lead not found." };
      }
    }
    return { error: "Something failed on our end. Try again." };
  }

  revalidatePath(`/admin/leads/${payload.leadId}`);
  revalidatePath("/admin/leads");
  return { ok: true };
}

// ── Scan feedback ───────────────────────────────────────────────────────
interface SubmitScanFeedbackPayload {
  scanId: string;
  reasoning: string;
}

export async function submitScanFeedbackAction(
  payload: SubmitScanFeedbackPayload,
) {
  const session = await currentSession();
  if (!session) return { error: "Session expired. Reload the page." };

  try {
    await apiFetch(`/admin/scans/${payload.scanId}/review`, {
      method: "POST",
      session,
      body: { reasoning: payload.reasoning },
    });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 422) return { error: "Feedback cannot be empty." };
      if (err.status === 404) return { error: "Scan not found." };
    }
    return { error: "Something failed on our end. Try again." };
  }

  revalidatePath("/admin/leads", "layout");
  return { ok: true };
}

// ── Email backfill ──────────────────────────────────────────────────────
interface SubmitEmailPayload {
  leadId: string;
  email: string;
}

export async function submitEmailBackfillAction(payload: SubmitEmailPayload) {
  const session = await currentSession();
  if (!session) return { error: "Session expired. Reload the page." };

  try {
    await apiFetch(`/admin/leads/${payload.leadId}/email`, {
      method: "POST",
      session,
      body: { email: payload.email },
    });
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 409) {
        return {
          error: "Email is already set for this lead. Ask eng to change it.",
        };
      }
      if (err.status === 422) return { error: "Enter a valid email address." };
      if (err.status === 404) return { error: "Lead not found." };
    }
    return { error: "Something failed on our end. Try again." };
  }

  revalidatePath(`/admin/leads/${payload.leadId}`);
  return { ok: true };
}

// ── Create analyst (superadmin only) ────────────────────────────────────
interface CreateAnalystPayload {
  username: string;
  password: string;
}

export async function createAnalystAction(payload: CreateAnalystPayload) {
  const session = await currentSession();
  if (!session) return { error: "Session expired. Reload the page." };

  try {
    const resp = await apiFetch<{ analyst_id: string; username: string }>(
      "/admin/analysts",
      { method: "POST", session, body: payload },
    );
    return { ok: true, analyst_id: resp.analyst_id, username: resp.username };
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 403) return { error: "Only superadmins can create analysts." };
      if (err.status === 409) return { error: `Username "${payload.username}" already exists.` };
      if (err.status === 422) return { error: "Username must be alphanumeric (a-z, 0-9, _, ., -). Password must be at least 8 characters." };
    }
    return { error: "Something failed on our end. Try again." };
  }
}

// ── Change password ─────────────────────────────────────────────────────
interface ChangePasswordPayload {
  currentPassword: string;
  newPassword: string;
}

export async function changePasswordAction(payload: ChangePasswordPayload) {
  const session = await currentSession();
  if (!session) return { error: "Session expired. Reload the page." };

  try {
    await apiFetch("/admin/auth/change-password", {
      method: "POST",
      session,
      body: {
        current_password: payload.currentPassword,
        new_password: payload.newPassword,
      },
    });
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 401) return { error: "Current password is incorrect." };
      if (err.status === 422) return { error: "New password must be at least 8 characters." };
    }
    return { error: "Something failed on our end. Try again." };
  }
}
