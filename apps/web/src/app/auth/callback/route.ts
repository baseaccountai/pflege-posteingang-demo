// GET /auth/callback – the IdP redirects here with the code (F01-AC3, F01-AC5).
// The login attempt is used up on the server and the login cookie is deleted in every
// case, so the callback works only once (also with a stolen cookie).
import { connection, type NextRequest } from "next/server";

import { completeLogin } from "@/lib/auth/callback";
import { parseEncKey } from "@/lib/auth/crypto";
import { LOGIN_COOKIE, openLoginState } from "@/lib/auth/login-state";
import { finishLogin, oidcConfig, oidcSettings } from "@/lib/auth/oidc";
import { clearCookie, redirectNoStore } from "@/lib/auth/responses";
import { SESSION_COOKIE, loginAttempts, sessionCookieOptions, sessionStore } from "@/lib/auth/session";

export async function GET(request: NextRequest) {
  await connection(); // per request, never prerendered at build time
  const settings = oidcSettings();
  const key = parseEncKey(process.env.SESSION_ENC_KEY);
  const state = openLoginState(request.cookies.get(LOGIN_COOKIE)?.value, key);

  const sid = await completeLogin(state, {
    consume: (value) => loginAttempts().consume(value),
    finish: async (value) => finishLogin(await oidcConfig(settings), settings, request.nextUrl, value),
    create: (session) => sessionStore().create(session),
  });

  const target = sid ? "/" : "/auth/error";
  const response = redirectNoStore(new URL(target, settings.appOrigin));
  clearCookie(response, LOGIN_COOKIE);
  if (sid) response.cookies.set(SESSION_COOKIE, sid, sessionCookieOptions());
  return response;
}
