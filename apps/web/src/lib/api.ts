// Server-side client for the FastAPI backend (design F01 "API-Client"). Every call carries
// the user's access token and a fresh BFF assertion (F01-AC8), so a token copied out of the
// BFF alone is not enough to call the API. Never import this into a client component.
import { createHash, createHmac } from "node:crypto";

const ASSERTION_LIFETIME_SECONDS = 60;
const MIN_SECRET_BYTES = 32;

/** The API rejected the token or the assertion: the session is no longer usable. */
export class ApiUnauthorized extends Error {}

const base64url = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");

/** HS256 JWS {sid_hash, aud, iat, exp}; checked by apps/api/app/auth/bff.py. */
export function bffAssertion(sid: string, secret: string, nowSeconds: number): string {
  if (Buffer.byteLength(secret) < MIN_SECRET_BYTES) {
    throw new Error("BFF_API_SECRET fehlt oder ist kürzer als 32 Bytes");
  }
  const header = base64url({ alg: "HS256", typ: "JWT" });
  const payload = base64url({
    sid_hash: createHash("sha256").update(sid).digest("hex"),
    aud: "pflege-api",
    iat: nowSeconds,
    exp: nowSeconds + ASSERTION_LIFETIME_SECONDS,
  });
  const signature = createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${signature}`;
}

export type Caller = { sid: string; accessToken: string };
export type ApiResult<T> = { status: 200; data: T } | { status: 404; data: null };

type Deps = { env?: NodeJS.ProcessEnv | Record<string, string | undefined>; fetch?: typeof fetch };

/** One API call in the caller's name: access token + a fresh BFF assertion, never cached. */
function callApi(
  path: string,
  caller: Caller,
  init: { method: string; body?: BodyInit; headers?: Record<string, string> },
  deps: Deps,
): Promise<Response> {
  const env = deps.env ?? process.env;
  const base = env.API_BASE_URL ?? "http://localhost:8000";
  const assertion = bffAssertion(caller.sid, env.BFF_API_SECRET ?? "", Math.floor(Date.now() / 1000));
  return (deps.fetch ?? fetch)(new URL(path, base).toString(), {
    ...init,
    cache: "no-store",
    // Auth headers last: a caller-supplied header can never replace them.
    headers: { ...init.headers, authorization: `Bearer ${caller.accessToken}`, "x-bff-assertion": assertion },
  });
}

/**
 * GET on the API in the caller's name. 404 is a normal answer (foreign and unknown look
 * the same, F01-AC12); 401 throws ApiUnauthorized; anything else throws.
 */
export async function apiGet<T>(path: string, caller: Caller, deps: Deps = {}): Promise<ApiResult<T>> {
  const response = await callApi(path, caller, { method: "GET" }, deps);
  if (response.status === 404) return { status: 404, data: null };
  if (response.status === 401) throw new ApiUnauthorized("API rejected token or assertion");
  if (!response.ok) throw new Error(`API answered ${response.status} for ${path}`);
  return { status: 200, data: (await response.json()) as T };
}

/** The session ended while the API call was running (logout or role switch elsewhere). */
export class SessionEnded extends Error {}

/**
 * Like apiGet, but the answer is only released if the session still exists afterwards:
 * a slow WB1 answer that arrives after a switch to WB2 is dropped (F01-AC13).
 */
export async function apiGetForSession<T>(
  path: string,
  caller: Caller,
  isActive: (sid: string) => Promise<boolean>,
  deps: Deps = {},
): Promise<ApiResult<T>> {
  const result = await apiGet<T>(path, caller, deps);
  if (!(await isActive(caller.sid))) throw new SessionEnded("session ended during the call");
  return result;
}

/**
 * A writing call (upload, retry). Client errors (403, 409, 413, 415, 422, 429) are passed on
 * with the API's {error_code, message}, so the app can show the reason; 401 and 5xx throw.
 */
export async function apiSend(
  path: string,
  caller: Caller,
  init: { method: "POST"; body?: BodyInit; headers?: Record<string, string> },
  deps: Deps = {},
): Promise<{ status: number; data: unknown }> {
  const response = await callApi(path, caller, init, deps);
  if (response.status === 401) throw new ApiUnauthorized("API rejected token or assertion");
  if (response.status >= 500) throw new Error(`API answered ${response.status} for ${path}`);
  return { status: response.status, data: await response.json().catch(() => null) };
}

/** The original file of a document (F03-AC4), or null if unknown or foreign (404). */
export async function apiFile(
  path: string,
  caller: Caller,
  deps: Deps = {},
): Promise<{ body: ArrayBuffer; contentType: string } | null> {
  const response = await callApi(path, caller, { method: "GET" }, deps);
  if (response.status === 404) return null;
  if (response.status === 401) throw new ApiUnauthorized("API rejected token or assertion");
  if (!response.ok) throw new Error(`API answered ${response.status} for ${path}`);
  return {
    body: await response.arrayBuffer(),
    contentType: response.headers.get("content-type") ?? "application/octet-stream",
  };
}
