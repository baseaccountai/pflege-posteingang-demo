// Session lookup for route handlers and server components (F01-AC3, F01-AC21).
// The cookie holds only the random session id; everything else stays on the server.
import postgres from "postgres";

import { SessionStore, parseEncKey, type Refreshed, type Session } from "./session-store";

/** __Host- prefix: the browser only accepts it with Secure, Path=/ and without Domain. */
export const SESSION_COOKIE = "__Host-pp_sid";

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: 8 * 3600, // same absolute end as the session row
  };
}

// newSessionId(): 32 bytes base64url = 43 characters.
const SESSION_ID = /^[A-Za-z0-9_-]{43}$/;

/**
 * The active session for the cookie value, or null (no cookie, expired, revoked, refresh
 * failed). Callers redirect to the start page with "Sitzung abgelaufen" on null.
 */
export async function loadSession(
  sid: string | undefined,
  store: Pick<SessionStore, "refreshIfDue">,
  refresh: (refreshToken: string) => Promise<Refreshed>,
): Promise<Session | null> {
  if (!sid || !SESSION_ID.test(sid)) return null;
  return store.refreshIfDue(sid, refresh);
}

let store: SessionStore | undefined;

/** One store per server process; BFF_DATABASE_URL is the bff_session role via the pooler. */
export function sessionStore(): SessionStore {
  if (!store) {
    const url = process.env.BFF_DATABASE_URL;
    if (!url) throw new Error("BFF_DATABASE_URL is not set");
    // prepare: false, because the Supabase transaction pooler does not keep prepared statements.
    const sql = postgres(url, { max: 5, prepare: false });
    store = new SessionStore(sql, parseEncKey(process.env.SESSION_ENC_KEY));
  }
  return store;
}
