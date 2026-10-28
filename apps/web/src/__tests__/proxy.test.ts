// @vitest-environment node
// F01-AC15: writing requests need Origin == APP_ORIGIN, otherwise 403.
// F11-AC11: every page gets its own nonce and the Content-Security-Policy.
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { proxy } from "../proxy";

const ORIGIN = "https://pflege.example";

function request(method: string, origin?: string) {
  const headers: Record<string, string> = origin === undefined ? {} : { origin };
  return new NextRequest(`${ORIGIN}/auth/logout`, { method, headers });
}

beforeEach(() => vi.stubEnv("APP_ORIGIN", ORIGIN));
afterEach(() => vi.unstubAllEnvs());

describe("proxy (CSRF)", () => {
  it.each(["GET", "HEAD"])("lets %s through", (method) => {
    expect(proxy(request(method)).status).not.toBe(403);
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"])("lets same-origin %s through", (method) => {
    expect(proxy(request(method, ORIGIN)).status).not.toBe(403);
  });

  it.each(["POST", "PUT", "PATCH", "DELETE"])("rejects %s without Origin", (method) => {
    expect(proxy(request(method)).status).toBe(403);
  });

  it.each(["https://evil.example", "null", `${ORIGIN}.evil.example`, "http://pflege.example"])(
    "rejects POST from %s",
    (origin) => {
      expect(proxy(request("POST", origin)).status).toBe(403);
    },
  );

  it("fails closed without APP_ORIGIN", () => {
    vi.stubEnv("APP_ORIGIN", "");
    expect(proxy(request("POST", ORIGIN)).status).toBe(403);
  });
});

describe("proxy (Content-Security-Policy)", () => {
  const get = (path: string) => proxy(new NextRequest(`${ORIGIN}${path}`));

  it("gives every page a fresh nonce in the CSP and passes it to the rendering", () => {
    const first = get("/bewohner");
    const second = get("/bewohner");
    const nonce = (response: Response) =>
      /'nonce-([^']+)'/.exec(response.headers.get("content-security-policy") ?? "")?.[1];
    expect(nonce(first)).toBeTruthy();
    expect(nonce(first)).not.toBe(nonce(second));
    // Next.js reads the nonce from the request's CSP header for its own scripts.
    expect(first.headers.get("x-middleware-request-content-security-policy")).toContain(`'nonce-${nonce(first)}'`);
    expect(first.headers.get("x-middleware-request-x-nonce")).toBe(nonce(first));
  });

  it.each(["/api/documents/d1/file", "/api/questions", "/offline.html", "/sw.js", "/icons/icon-192.png", "/manifest.webmanifest", "/muster/5eed.pdf"])(
    "leaves %s without the page CSP (no HTML page, or fixed headers)",
    (path) => {
      expect(get(path).headers.get("content-security-policy")).toBeNull();
    },
  );
});
