// @vitest-environment node
// F01-AC3 (cookie attributes), F01-AC21 (no or ended session -> null, caller redirects).
import { describe, expect, it, vi } from "vitest";

import { SESSION_COOKIE, endSession, loadSession, sessionCookieOptions } from "../session";
import type { Session, SessionStore } from "../session-store";

const SESSION = { sub: "u", appRole: "pdl" } as Session;

function fakeStore(result: Session | null) {
  return { refreshIfDue: vi.fn().mockResolvedValue(result) } as unknown as SessionStore & {
    refreshIfDue: ReturnType<typeof vi.fn>;
  };
}

describe("session cookie", () => {
  it("is a __Host- cookie: HttpOnly, Secure, SameSite=Lax, Path=/", () => {
    expect(SESSION_COOKIE).toBe("__Host-pp_sid");
    expect(sessionCookieOptions()).toMatchObject({
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
    });
  });

  it("outlives the 8 h session, so an expired session still shows the hint (AC21)", () => {
    expect(sessionCookieOptions().maxAge).toBe(7 * 24 * 3600);
  });
});

describe("loadSession", () => {
  const refresh = vi.fn();

  it("returns null without a cookie and without touching the database", async () => {
    const store = fakeStore(SESSION);
    expect(await loadSession(undefined, store, refresh)).toBeNull();
    expect(await loadSession("", store, refresh)).toBeNull();
    expect(store.refreshIfDue).not.toHaveBeenCalled();
  });

  it("ignores cookie values that cannot be a session id", async () => {
    const store = fakeStore(SESSION);
    expect(await loadSession("x".repeat(500), store, refresh)).toBeNull();
    expect(await loadSession("not base64url!", store, refresh)).toBeNull();
    expect(store.refreshIfDue).not.toHaveBeenCalled();
  });

  it("loads (and if due refreshes) the session for a well-formed id", async () => {
    const store = fakeStore(SESSION);
    const sid = "A".repeat(43);
    expect(await loadSession(sid, store, refresh)).toBe(SESSION);
    expect(store.refreshIfDue).toHaveBeenCalledWith(sid, refresh);
  });

  it("passes through an ended session as null", async () => {
    expect(await loadSession("A".repeat(43), fakeStore(null), refresh)).toBeNull();
  });
});

describe("endSession", () => {
  const sid = "A".repeat(43);
  const TOKENS = { access: "a", refresh: "r", id: null };

  function store(tokens: typeof TOKENS | null) {
    return { remove: vi.fn().mockResolvedValue(tokens) };
  }

  it("deletes the row and revokes exactly the tokens it held", async () => {
    const s = store(TOKENS);
    const revoke = vi.fn().mockResolvedValue(undefined);
    await endSession(sid, s, revoke);
    expect(s.remove).toHaveBeenCalledWith(sid);
    expect(revoke).toHaveBeenCalledWith(TOKENS);
  });

  it("does not revoke anything if there was no row", async () => {
    const revoke = vi.fn();
    await endSession(sid, store(null), revoke);
    expect(revoke).not.toHaveBeenCalled();
  });

  it("still ends the session locally if the IdP is unreachable", async () => {
    const s = store(TOKENS);
    await expect(
      endSession(sid, s, vi.fn().mockRejectedValue(new Error("discovery failed"))),
    ).resolves.toBeUndefined();
    expect(s.remove).toHaveBeenCalledWith(sid);
  });

  it("does nothing without a well-formed cookie", async () => {
    const s = store(TOKENS);
    await endSession(undefined, s, vi.fn());
    await endSession("bad", s, vi.fn());
    expect(s.remove).not.toHaveBeenCalled();
  });
});
