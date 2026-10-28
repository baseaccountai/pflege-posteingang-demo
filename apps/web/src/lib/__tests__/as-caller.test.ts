// @vitest-environment node
// F10-AC13: when the API sleeps, pages get a status instead of an error, BFF routes a 503
// with the start-up message; other failures still surface.
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/current", () => ({
  EXPIRED_PATH: "/?sitzung=abgelaufen",
  requireSession: vi.fn(async () => ({ sid: "sid-1", session: { tokens: { access: "a" } } })),
  currentSession: vi.fn(async () => ({ kind: "active", sid: "sid-1", session: { tokens: { access: "a" } } })),
}));
vi.mock("@/lib/auth/session", () => ({ sessionStore: () => ({ find: async () => ({}) }) }));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  apiGetForSession: vi.fn(),
}));

import { ApiUnavailable, apiGetForSession } from "@/lib/api";
import { API_STARTING_MESSAGE, bffRoute, getAsCaller } from "@/lib/as-caller";

describe("getAsCaller", () => {
  it("returns status 503 when the API is unavailable", async () => {
    vi.mocked(apiGetForSession).mockRejectedValueOnce(new ApiUnavailable("cold start"));
    expect(await getAsCaller("/residents")).toEqual({ status: 503, data: null });
  });

  it("still throws other errors", async () => {
    vi.mocked(apiGetForSession).mockRejectedValueOnce(new Error("API answered 500"));
    await expect(getAsCaller("/residents")).rejects.toThrow(/500/);
  });
});

describe("bffRoute", () => {
  it("answers 503 with the start-up message when the API is unavailable", async () => {
    const response = await bffRoute(async () => {
      throw new ApiUnavailable("cold start");
    });
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error_code: "api_starting", message: API_STARTING_MESSAGE });
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });

  it("passes the maintenance answer of the API through", async () => {
    const body = { error_code: "maintenance", message: "Demo wird gerade zurückgesetzt – bitte in einer Minute erneut versuchen" };
    const response = await bffRoute(async () => ({ status: 503, data: body }));
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual(body);
  });
});

it("the start-up message tells how long and what to do", () => {
  expect(API_STARTING_MESSAGE).toBe("Demo startet gerade … (bis zu 30 Sekunden) – bitte gleich erneut versuchen.");
});
