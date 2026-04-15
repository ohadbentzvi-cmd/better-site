/**
 * Edge middleware — signed-cookie auth for /admin routes.
 *
 * The admin console uses an HMAC-signed session cookie (see
 * web/lib/admin/session.ts). The login page is exempt; every other
 * /admin/* route redirects to /admin/login when the cookie is absent
 * or its signature fails.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  SESSION_COOKIE_NAME,
  SESSION_MAX_AGE,
  signSession,
  verifySession,
} from "@/lib/admin/session";

// Re-sign the cookie when its remaining life drops below this threshold.
// Using half the window keeps most requests free of signing overhead while
// still guaranteeing a long-idle user never loses a fresh session to a
// just-expired cookie.
const RESIGN_BEFORE_SECONDS = SESSION_MAX_AGE / 2;

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // Login page is always reachable.
  if (pathname === "/admin/login") {
    return NextResponse.next();
  }

  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const session = token ? await verifySession(token) : null;

  if (!session) {
    const loginUrl = new URL("/admin/login", request.url);
    loginUrl.searchParams.set("next", pathname + search);
    const res = NextResponse.redirect(loginUrl);
    if (token) {
      res.cookies.delete(SESSION_COOKIE_NAME);
    }
    return res;
  }

  const res = NextResponse.next();

  // Sliding expiration: if the cookie is older than half its max age, re-sign
  // it with a fresh exp. Active users stay signed in indefinitely; abandoned
  // sessions still expire.
  const nowSec = Math.floor(Date.now() / 1000);
  const remaining = (session.exp ?? 0) - nowSec;
  if (remaining > 0 && remaining < RESIGN_BEFORE_SECONDS) {
    try {
      const fresh = await signSession({
        analyst_id: session.analyst_id,
        username: session.username,
      });
      res.cookies.set(SESSION_COOKIE_NAME, fresh, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: SESSION_MAX_AGE,
      });
    } catch {
      // Signing failed (missing secret, etc). Let the user keep the old cookie
      // until it expires naturally; don't break the request.
    }
  }

  return res;
}

export const config = {
  matcher: "/admin/:path*",
};
