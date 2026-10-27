// Calls to the API in the name of the signed-in user, for pages and BFF route handlers.
// The session is checked before the call, and for reading calls again afterwards: a late
// answer of a session that ended meanwhile is never shown (F01-AC13).
import { NextResponse } from "next/server";
import { redirect } from "next/navigation";

import { ApiUnauthorized, SessionEnded, apiGetForSession, type ApiResult, type Caller } from "./api";
import { EXPIRED_PATH, currentSession, requireSession } from "./auth/current";
import { sessionStore } from "./auth/session";

const isActive = async (sid: string) => (await sessionStore().find(sid)) !== null;

/** Pages: GET in the caller's name; an ended session leads to the start page (F01-AC21). */
export async function getAsCaller<T>(path: string): Promise<ApiResult<T>> {
  const { sid, session } = await requireSession();
  let result: ApiResult<T>;
  try {
    result = await apiGetForSession<T>(path, { sid, accessToken: session.tokens.access }, isActive);
  } catch (error) {
    if (error instanceof ApiUnauthorized || error instanceof SessionEnded) redirect(EXPIRED_PATH);
    throw error;
  }
  return result;
}

const NO_STORE = { "Cache-Control": "private, no-store" };

export function jsonNoStore(data: unknown, status = 200) {
  return NextResponse.json(data, { status, headers: NO_STORE });
}

const SESSION_GONE = { error_code: "session_expired", message: "Sitzung abgelaufen – bitte Rolle wählen" };

/**
 * BFF route handlers: runs `call` with the caller, maps an ended session or a rejected token
 * to 401 (the browser then goes to the start page) and never lets the answer be cached.
 */
export async function bffRoute(
  call: (caller: Caller) => Promise<{ status: number; data: unknown }>,
): Promise<NextResponse> {
  const state = await currentSession();
  if (state.kind !== "active") return jsonNoStore(SESSION_GONE, 401);
  try {
    const { status, data } = await call({ sid: state.sid, accessToken: state.session.tokens.access });
    return jsonNoStore(data, status);
  } catch (error) {
    if (error instanceof ApiUnauthorized || error instanceof SessionEnded) {
      return jsonNoStore(SESSION_GONE, 401);
    }
    throw error;
  }
}

export { isActive };
