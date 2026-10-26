// POST /auth/logout[?next=/auth/login?role=…] – logout and role switch (F01-AC13).
// Origin is checked by proxy.ts (F01-AC15); there is no GET variant.
import type { NextRequest } from "next/server";

import { endSessionUrl, logoutTarget, oidcConfig, oidcSettings, revokeTokens } from "@/lib/auth/oidc";
import { clearCookie, redirectNoStore } from "@/lib/auth/responses";
import { SESSION_COOKIE, endSession, sessionStore } from "@/lib/auth/session";

export async function POST(request: NextRequest) {
  const settings = oidcSettings();
  // The row is deleted first; IdP discovery and revocation may fail without blocking that.
  await endSession(request.cookies.get(SESSION_COOKIE)?.value, sessionStore(), async (tokens) =>
    revokeTokens(await oidcConfig(settings), tokens),
  );

  // Role switch: straight to the next login (prompt=login asks for credentials again).
  // Logout: IdP logout page with client_id only, no token in the URL.
  const target = await logoutTarget(request.nextUrl.searchParams.get("next"), settings.appOrigin, async () =>
    endSessionUrl(await oidcConfig(settings), settings),
  );
  const response = redirectNoStore(target);
  clearCookie(response, SESSION_COOKIE);
  return response;
}
