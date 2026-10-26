// Shared response helpers of the auth route handlers.
import { NextResponse } from "next/server";

/**
 * Redirect that is never cached (F01-AC14). 303 makes the browser follow with GET,
 * also after the POST of a logout.
 */
export function redirectNoStore(url: URL | string, status: 302 | 303 = 303): NextResponse {
  const response = NextResponse.redirect(url, status);
  response.headers.set("Cache-Control", "no-store");
  return response;
}

/**
 * Deletes a __Host- cookie. The browser only accepts the deletion with the same
 * attributes (Secure, Path=/), which a plain cookies.delete() does not send.
 */
export function clearCookie(response: NextResponse, name: string): void {
  response.cookies.set(name, "", {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}
