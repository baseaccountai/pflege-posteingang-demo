// Login intermediate state (F01-AC5): state, nonce, PKCE verifier and the chosen role,
// encrypted in a short-lived cookie. The callback deletes it at once; the server-side
// attempt in login-attempts.ts makes it one-time even if the cookie was stolen.
// Contains no tokens.
import { openJson, sealJson } from "./crypto";
import { isRoleKey, type RoleKey } from "./roles";

export const LOGIN_COOKIE = "__Host-pp_oidc";
const LIFETIME_SECONDS = 600;
// Authenticated context: a ciphertext from another place (e.g. a session row) is rejected.
const CONTEXT = Buffer.from("pp_oidc login state v1");

export type LoginState = { state: string; nonce: string; verifier: string; role: RoleKey };

export function loginCookieOptions() {
  return {
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const, // sent on the top-level redirect back from the IdP
    path: "/",
    maxAge: LIFETIME_SECONDS,
  };
}

export function sealLoginState(value: LoginState, key: Buffer, now = Date.now()): string {
  const exp = now + LIFETIME_SECONDS * 1000;
  return sealJson({ ...value, exp }, key, CONTEXT).toString("base64url");
}

/** Null if missing, manipulated, from another context or older than 10 minutes. */
export function openLoginState(
  cookie: string | undefined,
  key: Buffer,
  now = Date.now(),
): LoginState | null {
  if (!cookie || cookie.length > 1024) return null;
  let data: LoginState & { exp: number };
  try {
    data = openJson(Buffer.from(cookie, "base64url"), key, CONTEXT);
  } catch {
    return null;
  }
  if (typeof data.exp !== "number" || now > data.exp || !isRoleKey(data.role)) return null;
  return { state: data.state, nonce: data.nonce, verifier: data.verifier, role: data.role };
}
