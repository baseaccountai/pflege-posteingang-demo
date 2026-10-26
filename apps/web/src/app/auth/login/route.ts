// GET /auth/login?role=wb1|wb2|pdl – starts the OIDC login for a demo role (F01-AC1).
import { connection, type NextRequest } from "next/server";

import { parseEncKey } from "@/lib/auth/crypto";
import { LOGIN_COOKIE, loginCookieOptions, sealLoginState } from "@/lib/auth/login-state";
import { oidcConfig, oidcSettings, revokeTokens, startLogin } from "@/lib/auth/oidc";
import { clearCookie, redirectNoStore } from "@/lib/auth/responses";
import { isRoleKey } from "@/lib/auth/roles";
import { SESSION_COOKIE, endSession, sessionStore } from "@/lib/auth/session";

export async function GET(request: NextRequest) {
  await connection(); // per request, never prerendered at build time
  const role = request.nextUrl.searchParams.get("role");
  const settings = oidcSettings();
  if (!isRoleKey(role)) return redirectNoStore(new URL("/", settings.appOrigin));

  const config = await oidcConfig(settings);
  // An existing session ends first: one browser, one role.
  await endSession(request.cookies.get(SESSION_COOKIE)?.value, sessionStore(), (tokens) =>
    revokeTokens(config, tokens),
  );

  const { url, state } = await startLogin(config, settings, role);
  const response = redirectNoStore(url, 302);
  const key = parseEncKey(process.env.SESSION_ENC_KEY);
  response.cookies.set(LOGIN_COOKIE, sealLoginState(state, key), loginCookieOptions());
  clearCookie(response, SESSION_COOKIE);
  return response;
}
