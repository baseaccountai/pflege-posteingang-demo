// Server-side client for the FastAPI backend (design F01 "API-Client"). Every call carries
// the user's access token and a fresh BFF assertion (F01-AC8), so a token copied out of the
// BFF alone is not enough to call the API. Never import this into a client component.
import { Agent } from "undici";
import { createHash, createHmac } from "node:crypto";

const ASSERTION_LIFETIME_SECONDS = 60;
const MIN_SECRET_BYTES = 32;

/** The API rejected the token or the assertion: the session is no longer usable. */
export class ApiUnauthorized extends Error {}

/**
 * The API does not answer (yet): cold start on Vercel, paused database, nightly reset.
 * Not an error of the app - the pages show "Demo startet gerade …" instead (F10-AC13).
 */
export class ApiUnavailable extends Error {}

/** Reads give up after this; a starting API then gets the start-up notice (F10-AC13). */
export const READ_TIMEOUT_MS = 5000;
const UNAVAILABLE = new Set([502, 503, 504]);

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

type Deps = {
  env?: NodeJS.ProcessEnv | Record<string, string | undefined>;
  fetch?: typeof fetch;
  /** Only for tests; reads otherwise use READ_TIMEOUT_MS. */
  timeoutMs?: number;
};

const apiBase = (deps: Deps) => (deps.env ?? process.env).API_BASE_URL ?? "http://localhost:8000";

/**
 * One API call in the caller's name: access token + a fresh BFF assertion, never cached.
 * No answer at all (network error, timeout) becomes ApiUnavailable.
 */
async function callApi(
  path: string,
  caller: Caller,
  init: {
    method: string;
    body?: BodyInit;
    headers?: Record<string, string>;
    signal?: AbortSignal;
    dispatcher?: Agent; // undici option of Node's fetch (local mode, see longWait)
  },
  deps: Deps,
): Promise<Response> {
  const env = deps.env ?? process.env;
  const assertion = bffAssertion(caller.sid, env.BFF_API_SECRET ?? "", Math.floor(Date.now() / 1000));
  try {
    return await (deps.fetch ?? fetch)(new URL(path, apiBase(deps)).toString(), {
      ...(init as RequestInit),
      cache: "no-store",
      // Auth headers last: a caller-supplied header can never replace them.
      headers: { ...init.headers, authorization: `Bearer ${caller.accessToken}`, "x-bff-assertion": assertion },
    });
  } catch (error) {
    throw new ApiUnavailable(`API not reachable for ${path}`, { cause: error });
  }
}

/**
 * Fully local mode only (F11, `make up-local`): a CPU model needs minutes for an answer, but
 * Node's fetch gives up after 300 s without the first byte. API_WAIT_SECONDS raises that for
 * writing calls; without it nothing changes (public demo).
 */
function longWait(deps: Deps): { dispatcher?: Agent } {
  const seconds = Number((deps.env ?? process.env).API_WAIT_SECONDS);
  if (!Number.isFinite(seconds) || seconds <= 0) return {};
  waitingAgent ??= new Agent({ headersTimeout: seconds * 1000, bodyTimeout: seconds * 1000 });
  return { dispatcher: waitingAgent };
}
let waitingAgent: Agent | undefined;

const readSignal = (deps: Deps) => AbortSignal.timeout(deps.timeoutMs ?? READ_TIMEOUT_MS);

/**
 * GET on the API in the caller's name. 404 is a normal answer (foreign and unknown look
 * the same, F01-AC12); 401 throws ApiUnauthorized; no answer within 5 s or 502/503/504
 * throws ApiUnavailable (F10-AC13); anything else throws.
 */
export async function apiGet<T>(path: string, caller: Caller, deps: Deps = {}): Promise<ApiResult<T>> {
  const response = await callApi(path, caller, { method: "GET", signal: readSignal(deps) }, deps);
  if (response.status === 404) return { status: 404, data: null };
  if (response.status === 401) throw new ApiUnauthorized("API rejected token or assertion");
  if (UNAVAILABLE.has(response.status)) throw new ApiUnavailable(`API answered ${response.status} for ${path}`);
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
 * A writing call (upload, retry). Client errors (403, 409, 413, 415, 422, 429) and the
 * maintenance 503 of the nightly reset (F10-AC7) are passed on with the API's
 * {error_code, message}, so the app can show the reason. 401 throws ApiUnauthorized,
 * no answer or 502/503/504 ApiUnavailable, other 5xx an error. No timeout: an upload to a
 * starting API may take longer than a read.
 */
export async function apiSend(
  path: string,
  caller: Caller,
  init: { method: "POST"; body?: BodyInit; headers?: Record<string, string> },
  deps: Deps = {},
): Promise<{ status: number; data: unknown }> {
  const response = await callApi(path, caller, { ...init, ...longWait(deps) }, deps);
  if (response.status === 401) throw new ApiUnauthorized("API rejected token or assertion");
  const data = await response.json().catch(() => null);
  // A 503 with the API's own error code (reset, model or agent not reachable) carries a
  // message for the user; only a 503 without one means the API itself is not up yet.
  if (response.status === 503 && typeof data?.error_code === "string" && typeof data?.message === "string") {
    return { status: 503, data };
  }
  if (UNAVAILABLE.has(response.status)) throw new ApiUnavailable(`API answered ${response.status} for ${path}`);
  if (response.status >= 500) throw new Error(`API answered ${response.status} for ${path}`);
  return { status: response.status, data };
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

/**
 * Is the API up, with its database? Public health check, no token (F10-AC9, AC13): the
 * start-up notice asks this every 5 s before it reloads the page.
 */
export async function apiReady(deps: Deps = {}): Promise<boolean> {
  try {
    const response = await (deps.fetch ?? fetch)(new URL("/health/ready", apiBase(deps)).toString(), {
      cache: "no-store",
      signal: readSignal(deps),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export type AgentTokenWay = "exchange" | "self_signed" | "off";
const AGENT_TOKEN_WAYS: AgentTokenWay[] = ["exchange", "self_signed", "off"];

/**
 * Which way the API gets the agent's token (F08-AC2), from its public health check - so
 * /projekt names the way really in use. null: the API does not answer (yet).
 */
export async function apiAgentTokenWay(deps: Deps = {}): Promise<AgentTokenWay | null> {
  try {
    const response = await (deps.fetch ?? fetch)(new URL("/health", apiBase(deps)).toString(), {
      cache: "no-store",
      signal: readSignal(deps),
    });
    const way = (await response.json())?.agent_token;
    return AGENT_TOKEN_WAYS.includes(way) ? way : null;
  } catch {
    return null;
  }
}

/** Like apiFile, but the file is only released if the session still exists afterwards (F01-AC13). */
export async function apiFileForSession(
  path: string,
  caller: Caller,
  isActive: (sid: string) => Promise<boolean>,
  deps: Deps = {},
): Promise<{ body: ArrayBuffer; contentType: string } | null> {
  const file = await apiFile(path, caller, deps);
  if (!(await isActive(caller.sid))) throw new SessionEnded("session ended during the download");
  return file;
}

/**
 * Like apiSend, but the answer is only released if the session still exists afterwards:
 * an answer to a WB1 question that arrives after a switch to WB2 is dropped (F05-AC11).
 */
export async function apiSendForSession(
  path: string,
  caller: Caller,
  init: { method: "POST"; body?: BodyInit; headers?: Record<string, string> },
  isActive: (sid: string) => Promise<boolean>,
  deps: Deps = {},
): Promise<{ status: number; data: unknown }> {
  const result = await apiSend(path, caller, init, deps);
  if (!(await isActive(caller.sid))) throw new SessionEnded("session ended during the call");
  return result;
}
