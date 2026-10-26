// The session of the current request, for server components (F01-AC21). Reads the cookie,
// so callers sit behind a <Suspense> boundary (Cache Components).
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { oidcConfig, refreshTokens } from "./oidc";
import { SESSION_COOKIE, loadSession, sessionStore } from "./session";
import type { Session } from "./session-store";

export type SessionState =
  | { kind: "none" }
  | { kind: "ended" }
  | { kind: "active"; sid: string; session: Session };

export const EXPIRED_PATH = "/?sitzung=abgelaufen";

/** Once per request (header and page share it); never cached across requests. */
export const currentSession = cache(async (): Promise<SessionState> => {
  const sid = (await cookies()).get(SESSION_COOKIE)?.value;
  // Without a cookie the database is not touched (anonymous visitors of the start page).
  if (!sid) return { kind: "none" };
  const config = await oidcConfig();
  const session = await loadSession(sid, sessionStore(), (token) => refreshTokens(config, token));
  return session ? { kind: "active", sid, session } : { kind: "ended" };
});

/** Pages with user data: start page without a session, with the hint once it has ended. */
export async function requireSession(): Promise<{ sid: string; session: Session }> {
  const state = await currentSession();
  if (state.kind === "none") redirect("/");
  if (state.kind === "ended") redirect(EXPIRED_PATH);
  return state;
}
