/**
 * Edge middleware — HTTP basic auth for /admin routes.
 *
 * Credentials come from ADMIN_BASIC_AUTH_USER and ADMIN_BASIC_AUTH_PASSWORD
 * env vars. See `.env.example`.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const authHeader = request.headers.get("authorization");
  const expectedUser = process.env.ADMIN_BASIC_AUTH_USER ?? "";
  const expectedPass = process.env.ADMIN_BASIC_AUTH_PASSWORD ?? "";

  if (!expectedUser || !expectedPass) {
    // Fail closed — admin is inaccessible until credentials are set.
    return new NextResponse("admin auth not configured", { status: 503 });
  }

  if (authHeader?.startsWith("Basic ")) {
    const decoded = atob(authHeader.slice(6));
    const [user, pass] = decoded.split(":");
    if (user === expectedUser && pass === expectedPass) {
      return NextResponse.next();
    }
  }

  return new NextResponse("authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="BetterSite Admin"' },
  });
}

export const config = {
  matcher: "/admin/:path*",
};
