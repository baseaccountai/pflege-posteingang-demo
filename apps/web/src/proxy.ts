// Runs before every request (Next.js "proxy", formerly middleware).
//
// 1. CSRF protection (F01-AC15): a writing request is only accepted if the browser says it
//    comes from our own origin. SameSite=Lax on the session cookie is the second layer.
// 2. Content-Security-Policy with a fresh nonce for every page (F11-AC11). Next.js reads
//    the nonce from the request's CSP header and puts it on its own scripts.
import { NextResponse, type NextRequest } from "next/server";

import { contentSecurityPolicy } from "@/lib/security/csp";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
// No HTML pages (API answers, the original PDF in the browser's viewer) or static files
// with fixed headers from next.config.ts: no page CSP.
const WITHOUT_PAGE_CSP = /^\/(api\/|icons\/|muster\/|offline\.html$|sw\.js$|manifest\.webmanifest$)/;

export function proxy(request: NextRequest) {
  if (!SAFE_METHODS.has(request.method)) {
    const allowed = process.env.APP_ORIGIN;
    const origin = request.headers.get("origin");
    if (!allowed || origin !== allowed) {
      return new NextResponse("Anfrage abgelehnt", { status: 403 });
    }
  }
  if (WITHOUT_PAGE_CSP.test(request.nextUrl.pathname)) return NextResponse.next();

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy(nonce, process.env.OIDC_ISSUER, process.env.NODE_ENV === "development");
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("content-security-policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("content-security-policy", csp);
  return response;
}

export const config = {
  // Build files never take writes and need no page CSP; everything else is checked.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
