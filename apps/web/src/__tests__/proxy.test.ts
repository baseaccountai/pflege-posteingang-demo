// @vitest-environment node
// F01-AC15: writing requests need Origin == APP_ORIGIN, otherwise 403.
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
