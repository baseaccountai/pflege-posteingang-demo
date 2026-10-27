// GET /auth/login?role=wb1|wb2|pdl – starts the OIDC login for a demo role (F01-AC1).
import { connection, type NextRequest } from "next/server";

import { parseEncKey } from "@/lib/auth/crypto";
import { LOGIN_COOKIE, loginCookieOptions, sealLoginState } from "@/lib/auth/login-state";
import { oidcConfig, oidcSettings, revokeTokens, startLogin } from "@/lib/auth/oidc";
import { clearCookie, redirectNoStore } from "@/lib/auth/responses";
import { isRoleKey } from "@/lib/auth/roles";
import {
  SESSION_COOKIE,
  endSession,
  hasActiveSession,
  loginAttempts,
  sessionStore,
} from "@/lib/auth/session";

export async function GET(request: NextRequest) {
  await connection(); // per request, never prerendered at build time
  const role = request.nextUrl.searchParams.get("role");
  const settings = oidcSettings();
  if (!isRoleKey(role)) return redirectNoStore(new URL("/", settings.appOrigin));

  // An active session is never ended by a GET: a foreign page could otherwise log the
  // visitor out with a plain link. Role switching goes through POST /auth/logout?next=…
  // (Origin-checked, F01-AC15); the start page shows the role buttons.
  const sid = request.cookies.get(SESSION_COOKIE)?.value;
  if (await hasActiveSession(sid)) return redirectNoStore(new URL("/", settings.appOrigin), 302);

  const config = await oidcConfig(settings);
  // Leftovers of an ended session (expired or revoked row) are removed.
  await endSession(sid, sessionStore(), (tokens) => revokeTokens(config, tokens));

  const { url, state } = await startLogin(config, settings, role);
  await loginAttempts().begin(state.state); // one-time, checked by the callback (AC5)
  const response = redirectNoStore(url, 302);
  const key = parseEncKey(process.env.SESSION_ENC_KEY);
  response.cookies.set(LOGIN_COOKIE, sealLoginState(state, key), loginCookieOptions());
  clearCookie(response, SESSION_COOKIE);
  return response;
}
