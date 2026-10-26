// POST /auth/logout[?next=/auth/login?role=…] – logout and role switch (F01-AC13).
// Origin is checked by proxy.ts (F01-AC15); there is no GET variant.
import type { NextRequest } from "next/server";

import { endSessionUrl, oidcConfig, oidcSettings, revokeTokens, safeNext } from "@/lib/auth/oidc";
import { clearCookie, redirectNoStore } from "@/lib/auth/responses";
import { SESSION_COOKIE, endSession, sessionStore } from "@/lib/auth/session";

export async function POST(request: NextRequest) {
  const settings = oidcSettings();
  const config = await oidcConfig(settings);
  await endSession(request.cookies.get(SESSION_COOKIE)?.value, sessionStore(), (tokens) =>
    revokeTokens(config, tokens),
  );

  // Role switch: straight to the next login (prompt=login asks for credentials again).
  // Logout: IdP logout page with client_id only, no token in the URL.
  const next = safeNext(request.nextUrl.searchParams.get("next"));
  const target = next ? new URL(next, settings.appOrigin) : endSessionUrl(config, settings);
  const response = redirectNoStore(target);
  clearCookie(response, SESSION_COOKIE);
  return response;
}
