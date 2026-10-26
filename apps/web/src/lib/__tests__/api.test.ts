// @vitest-environment node
// F01-AC8 (BFF assertion), F01-AC14 (no caching of user data), F01-AC21 (401 -> session gone).
import { createHash, createHmac } from "node:crypto";
import { describe, expect, it, vi } from "vitest";

import { ApiUnauthorized, apiGet, bffAssertion } from "../api";

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
  });
});
