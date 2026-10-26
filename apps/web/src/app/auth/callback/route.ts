// GET /auth/callback – the IdP redirects here with the code (F01-AC3, F01-AC5).
// The login state cookie is deleted in every case, so the callback works only once.
import { connection, type NextRequest } from "next/server";

import { parseEncKey } from "@/lib/auth/crypto";
import { LOGIN_COOKIE, openLoginState } from "@/lib/auth/login-state";
import { finishLogin, oidcConfig, oidcSettings } from "@/lib/auth/oidc";
import { clearCookie, redirectNoStore } from "@/lib/auth/responses";
import { SESSION_COOKIE, sessionCookieOptions, sessionStore } from "@/lib/auth/session";

export async function GET(request: NextRequest) {
  await connection(); // per request, never prerendered at build time
  const settings = oidcSettings();
  const key = parseEncKey(process.env.SESSION_ENC_KEY);
  const state = openLoginState(request.cookies.get(LOGIN_COOKIE)?.value, key);

  let sid: string | null = null;
  if (state) {
    try {
      const config = await oidcConfig(settings);
      const session = await finishLogin(config, settings, request.nextUrl, state);
      sid = await sessionStore().create(session);
    } catch (error) {
      // Wrong state/nonce/PKCE, reused or expired code, IdP error, no known role.
      // Logged without details: messages could contain parts of the request.
      console.warn("login callback rejected:", (error as Error).name);
    }
  }

  const target = sid ? "/" : "/auth/error";
  const response = redirectNoStore(new URL(target, settings.appOrigin));
  clearCookie(response, LOGIN_COOKIE);
  if (sid) response.cookies.set(SESSION_COOKIE, sid, sessionCookieOptions());
  return response;
}
