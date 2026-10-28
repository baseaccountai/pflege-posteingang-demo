// @vitest-environment node
// F01-AC8 (BFF assertion), F01-AC14 (no caching of user data), F01-AC21 (401 -> session gone).
import { createHash, createHmac } from "node:crypto";
import { describe, expect, it, vi } from "vitest";

import {
  ApiUnauthorized,
  ApiUnavailable,
  READ_TIMEOUT_MS,
  SessionEnded,
  apiGet,
  apiReady,
  apiFile,
  apiFileForSession,
  apiGetForSession,
  apiSend,
  apiSendForSession,
  bffAssertion,
} from "../api";

const SECRET = "s".repeat(32);
const SID = "A".repeat(43);

function decode(jws: string) {
  const [header, payload, signature] = jws.split(".");
  const expected = createHmac("sha256", SECRET).update(`${header}.${payload}`).digest("base64url");
  return {
    header: JSON.parse(Buffer.from(header, "base64url").toString()),
    payload: JSON.parse(Buffer.from(payload, "base64url").toString()),
    valid: signature === expected,
  };
}

describe("bffAssertion", () => {
  it("is an HS256 JWS with sid_hash, aud pflege-api and 60 s lifetime", () => {
    const { header, payload, valid } = decode(bffAssertion(SID, SECRET, 1_000_000));
    expect(valid).toBe(true);
    expect(header).toEqual({ alg: "HS256", typ: "JWT" });
    expect(payload).toEqual({
      sid_hash: createHash("sha256").update(SID).digest("hex"),
      aud: "pflege-api",
      iat: 1_000_000,
      exp: 1_000_060,
    });
  });

  it("refuses a secret shorter than 32 bytes", () => {
    expect(() => bffAssertion(SID, "short", 1)).toThrow(/BFF_API_SECRET/);
  });
});

describe("apiGet", () => {
  const env = { API_BASE_URL: "http://api.test", BFF_API_SECRET: SECRET };
  const caller = { sid: SID, accessToken: "access-123" };

  function fakeFetch(status: number, body: unknown = {}) {
    return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  }

  it("sends the access token and a fresh BFF assertion, never cached", async () => {
    const fetch = fakeFetch(200, [{ id: "1" }]);
    const result = await apiGet("/residents", caller, { env, fetch });
    expect(result).toEqual({ status: 200, data: [{ id: "1" }] });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("http://api.test/residents");
    expect(init.cache).toBe("no-store");
    expect(init.headers.authorization).toBe("Bearer access-123");
    expect(decode(init.headers["x-bff-assertion"]).valid).toBe(true);
  });

  it("returns 404 as a status, so foreign and unknown look the same", async () => {
    expect(await apiGet("/residents/x", caller, { env, fetch: fakeFetch(404) })).toEqual({
      status: 404,
      data: null,
    });
  });

  it("throws ApiUnauthorized on 401 (token or assertion rejected)", async () => {
    await expect(apiGet("/me", caller, { env, fetch: fakeFetch(401) })).rejects.toBeInstanceOf(
      ApiUnauthorized,
    );
  });

  it("throws on other errors instead of showing partial data", async () => {
    await expect(apiGet("/me", caller, { env, fetch: fakeFetch(500) })).rejects.toThrow(/500/);
    await expect(apiGet("/me", caller, { env, fetch: fakeFetch(500) })).rejects.not.toBeInstanceOf(
      ApiUnavailable,
    );
  });

  // F10-AC13: a sleeping or starting API is not an error of the app.
  it.each([502, 503, 504])("throws ApiUnavailable on %i", async (status) => {
    await expect(apiGet("/me", caller, { env, fetch: fakeFetch(status) })).rejects.toBeInstanceOf(
      ApiUnavailable,
    );
  });

  it("throws ApiUnavailable when the API cannot be reached", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    await expect(apiGet("/me", caller, { env, fetch })).rejects.toBeInstanceOf(ApiUnavailable);
  });

  it("gives up waiting after the read timeout (5 s)", async () => {
    expect(READ_TIMEOUT_MS).toBe(5000);
    // Answers only when aborted - like an API that is still starting.
    const fetch = vi.fn(
      (_url: URL | RequestInfo, init?: RequestInit) =>
        new Promise<Response>((_, reject) => init!.signal!.addEventListener("abort", () => reject(init!.signal!.reason))),
    );
    await expect(apiGet("/me", caller, { env, fetch, timeoutMs: 20 })).rejects.toBeInstanceOf(ApiUnavailable);
  });
});

describe("apiGetForSession", () => {
  const env = { API_BASE_URL: "http://api.test", BFF_API_SECRET: SECRET };
  const caller = { sid: SID, accessToken: "access-123" };
  const fetch = () => vi.fn().mockResolvedValue(new Response(JSON.stringify([{ id: "wb1" }])));

  it("releases the data while the session still exists", async () => {
    const isActive = vi.fn().mockResolvedValue(true);
    const result = await apiGetForSession("/residents", caller, isActive, { env, fetch: fetch() });
    expect(result.data).toEqual([{ id: "wb1" }]);
    expect(isActive).toHaveBeenCalledWith(SID);
  });

  it("withholds a late answer if the session ended meanwhile (role switch, AC13)", async () => {
    const isActive = vi.fn().mockResolvedValue(false);
    await expect(
      apiGetForSession("/residents", caller, isActive, { env, fetch: fetch() }),
    ).rejects.toBeInstanceOf(SessionEnded);
  });
});

describe("apiSend", () => {
  const env = { API_BASE_URL: "http://api.test", BFF_API_SECRET: SECRET };
  const caller = { sid: SID, accessToken: "access-123" };
  const answer = (status: number, body: unknown) =>
    vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));

  it("forwards method and body with token and BFF assertion, never cached", async () => {
    const fetch = answer(202, { id: "d1", status: "uploaded" });
    const body = new FormData();
    body.set("ward_id", "wb2");
    const result = await apiSend("/documents", caller, { method: "POST", body }, { env, fetch });
    expect(result).toEqual({ status: 202, data: { id: "d1", status: "uploaded" } });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("http://api.test/documents");
    expect(init).toMatchObject({ method: "POST", body, cache: "no-store" });
    expect(init.headers.authorization).toBe("Bearer access-123");
    expect(decode(init.headers["x-bff-assertion"]).valid).toBe(true);
  });

  it("keeps the content type of a JSON body, but the auth headers cannot be overridden", async () => {
    const fetch = answer(200, {});
    await apiSend(
      "/documents/d1/approve",
      caller,
      { method: "POST", body: "{}", headers: { "content-type": "application/json", authorization: "Bearer evil" } },
      { env, fetch },
    );
    const { headers } = fetch.mock.calls[0][1];
    expect(headers["content-type"]).toBe("application/json");
    expect(headers.authorization).toBe("Bearer access-123");
  });

  it.each([403, 409, 413, 415, 422, 429])("passes %i with its error body through", async (status) => {
    const body = { error_code: "x", message: "Grund" };
    expect(await apiSend("/documents", caller, { method: "POST" }, { env, fetch: answer(status, body) })).toEqual({
      status,
      data: body,
    });
  });

  // F10-AC7: the reset's message reaches the user.
  it("passes the maintenance 503 with its message through", async () => {
    const body = { error_code: "maintenance", message: "Demo wird gerade zurückgesetzt" };
    expect(await apiSend("/x", caller, { method: "POST" }, { env, fetch: answer(503, body) })).toEqual({
      status: 503,
      data: body,
    });
  });

  it.each([502, 503, 504])("throws ApiUnavailable on %i without maintenance", async (status) => {
    await expect(apiSend("/x", caller, { method: "POST" }, { env, fetch: answer(status, {}) })).rejects.toBeInstanceOf(
      ApiUnavailable,
    );
  });

  it("throws ApiUnavailable when the API cannot be reached", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    await expect(apiSend("/x", caller, { method: "POST" }, { env, fetch })).rejects.toBeInstanceOf(ApiUnavailable);
  });

  it("throws ApiUnauthorized on 401 and an error on 5xx", async () => {
    await expect(apiSend("/x", caller, { method: "POST" }, { env, fetch: answer(401, {}) })).rejects.toBeInstanceOf(
      ApiUnauthorized,
    );
    await expect(apiSend("/x", caller, { method: "POST" }, { env, fetch: answer(500, {}) })).rejects.toThrow(/500/);
  });
});

describe("apiFile", () => {
  const env = { API_BASE_URL: "http://api.test", BFF_API_SECRET: SECRET };
  const caller = { sid: SID, accessToken: "access-123" };

  it("returns bytes and type of the original, or null when not found", async () => {
    const pdf = new Uint8Array([0x25, 0x50, 0x44, 0x46]);
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(pdf, { status: 200, headers: { "content-type": "application/pdf" } }))
      .mockResolvedValueOnce(new Response("{}", { status: 404 }));
    const file = await apiFile("/documents/d1/file", caller, { env, fetch });
    expect(file?.contentType).toBe("application/pdf");
    expect(new Uint8Array(file!.body)).toEqual(pdf);
    expect(fetch.mock.calls[0][1].headers.authorization).toBe("Bearer access-123");
    expect(await apiFile("/documents/x/file", caller, { env, fetch })).toBeNull();
  });
});

describe("apiReady", () => {
  const env = { API_BASE_URL: "http://api.test" };

  it("asks /health/ready of the API (no user data, no token)", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"db":"ok"}', { status: 200 }));
    expect(await apiReady({ env, fetch })).toBe(true);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("http://api.test/health/ready");
    expect(init.headers).toBeUndefined();
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("is false when the API or its database is not ready", async () => {
    expect(await apiReady({ env, fetch: vi.fn().mockResolvedValue(new Response("{}", { status: 503 })) })).toBe(false);
    expect(await apiReady({ env, fetch: vi.fn().mockRejectedValue(new TypeError("fetch failed")) })).toBe(false);
  });
});

// Codex review Phase 3 #4: a slow original of WB1 must not arrive after a switch to WB2
// (F01-AC13), like the JSON reads.
describe("apiFileForSession", () => {
  const env = { API_BASE_URL: "http://api.test", BFF_API_SECRET: SECRET };
  const caller = { sid: SID, accessToken: "access-123" };
  const pdf = () =>
    vi.fn().mockResolvedValue(new Response(new Uint8Array([0x25, 0x50]), { headers: { "content-type": "application/pdf" } }));

  it("releases the file while the session still exists", async () => {
    const isActive = vi.fn().mockResolvedValue(true);
    const file = await apiFileForSession("/documents/d1/file", caller, isActive, { env, fetch: pdf() });
    expect(file?.contentType).toBe("application/pdf");
    expect(isActive).toHaveBeenCalledWith(SID);
  });

  it("withholds the file if the session ended during the download", async () => {
    const isActive = vi.fn().mockResolvedValue(false);
    await expect(
      apiFileForSession("/documents/d1/file", caller, isActive, { env, fetch: pdf() }),
    ).rejects.toBeInstanceOf(SessionEnded);
  });
});

// F05-AC11: an answer that arrives after a role switch is never delivered.
describe("apiSendForSession", () => {
  const env = { API_BASE_URL: "http://api.test", BFF_API_SECRET: SECRET };
  const caller = { sid: SID, accessToken: "access-123" };
  const answer = () => vi.fn().mockResolvedValue(new Response(JSON.stringify({ answer: "x" }), { status: 200 }));

  it("passes the answer on while the session still exists", async () => {
    const isActive = vi.fn().mockResolvedValue(true);
    const result = await apiSendForSession("/questions", caller, { method: "POST" }, isActive, { env, fetch: answer() });
    expect(result).toEqual({ status: 200, data: { answer: "x" } });
    expect(isActive).toHaveBeenCalledWith(SID);
  });

  it("withholds the answer if the session ended meanwhile", async () => {
    const isActive = vi.fn().mockResolvedValue(false);
    await expect(
      apiSendForSession("/questions", caller, { method: "POST" }, isActive, { env, fetch: answer() }),
    ).rejects.toBeInstanceOf(SessionEnded);
  });
});
