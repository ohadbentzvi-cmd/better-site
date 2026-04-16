/**
 * Admin session cookie — HMAC-signed via jose.
 *
 * Cookie payload: { analyst_id, username, exp }.
 * 7-day sliding expiration: middleware extends on each authed request.
 */

import { SignJWT, jwtVerify } from "jose";

export const SESSION_COOKIE_NAME = "bettersite_admin_session";
const SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

export interface AdminSession {
  analyst_id: string;
  username: string;
  is_superadmin: boolean;
  exp?: number;
}

function getSecretKey(): Uint8Array {
  const secret = process.env.ADMIN_SESSION_SECRET ?? "";
  if (secret.length < 32) {
    throw new Error(
      "ADMIN_SESSION_SECRET missing or shorter than 32 bytes. Refusing to sign admin sessions.",
    );
  }
  return new TextEncoder().encode(secret);
}

export async function signSession(payload: {
  analyst_id: string;
  username: string;
  is_superadmin: boolean;
}): Promise<string> {
  return await new SignJWT({ ...payload })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${SESSION_MAX_AGE_SECONDS}s`)
    .sign(getSecretKey());
}

export async function verifySession(token: string): Promise<AdminSession | null> {
  try {
    const { payload } = await jwtVerify(token, getSecretKey(), {
      algorithms: ["HS256"],
    });
    if (
      typeof payload.analyst_id !== "string" ||
      typeof payload.username !== "string"
    ) {
      return null;
    }
    return {
      analyst_id: payload.analyst_id,
      username: payload.username,
      is_superadmin: payload.is_superadmin === true,
      exp: typeof payload.exp === "number" ? payload.exp : undefined,
    };
  } catch {
    return null;
  }
}

export const SESSION_MAX_AGE = SESSION_MAX_AGE_SECONDS;
