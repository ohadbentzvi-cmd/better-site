/**
 * Server-side fetch wrapper for FastAPI /admin/* endpoints.
 *
 * Adds X-Service-Token on every request. Adds X-Analyst-Id when a session
 * is provided (all authed endpoints require it). Throws ApiError with the
 * HTTP status so route handlers can translate into UI errors.
 */

import "server-only";
import type { AdminSession } from "./session";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

function baseUrl(): string {
  const url = process.env.API_BASE_URL ?? "http://localhost:8000";
  return url.replace(/\/$/, "");
}

function serviceToken(): string {
  const t = process.env.ADMIN_SERVICE_TOKEN ?? "";
  if (t.length < 16) {
    throw new Error(
      "ADMIN_SERVICE_TOKEN not configured. Refusing to call admin API.",
    );
  }
  return t;
}

export async function apiFetch<T>(
  path: string,
  opts: {
    method?: "GET" | "POST";
    session?: AdminSession | null;
    body?: unknown;
    cache?: RequestCache;
  } = {},
): Promise<T> {
  const { method = "GET", session = null, body, cache = "no-store" } = opts;

  const headers: Record<string, string> = {
    "X-Service-Token": serviceToken(),
    "Content-Type": "application/json",
  };
  if (session) {
    headers["X-Analyst-Id"] = session.analyst_id;
  }

  const res = await fetch(`${baseUrl()}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache,
  });

  const text = await res.text();
  let parsed: unknown = null;
  if (text.length) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, parsed, `API ${method} ${path} -> ${res.status}`);
  }
  return parsed as T;
}
