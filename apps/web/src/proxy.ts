// CSRF protection (F01-AC15): a writing request is only accepted if the browser says it
// comes from our own origin. SameSite=Lax on the session cookie is the second layer.
import { NextResponse, type NextRequest } from "next/server";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function proxy(request: NextRequest) {
  if (SAFE_METHODS.has(request.method)) return NextResponse.next();
  const allowed = process.env.APP_ORIGIN;
  const origin = request.headers.get("origin");
  if (!allowed || origin !== allowed) {
    return new NextResponse("Anfrage abgelehnt", { status: 403 });
  }
  return NextResponse.next();
}

export const config = {
  // Static files never take writes; everything else (pages, route handlers) is checked.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
