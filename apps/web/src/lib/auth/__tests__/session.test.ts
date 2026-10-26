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
    expect(sessionCookieOptions()).toEqual({
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: 8 * 3600,
    });
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

  function store(session: Session | null) {
    return {
      find: vi.fn().mockResolvedValue(session),
      delete: vi.fn().mockResolvedValue(undefined),
    };
  }

  it("revokes the tokens at the IdP and deletes the row", async () => {
    const s = store({ ...SESSION, tokens: { access: "a", refresh: "r", id: null } });
    const revoke = vi.fn().mockResolvedValue(undefined);
    await endSession(sid, s, revoke);
    expect(revoke).toHaveBeenCalledWith({ access: "a", refresh: "r", id: null });
    expect(s.delete).toHaveBeenCalledWith(sid);
  });

  it("still deletes the row of an expired or revoked session", async () => {
    const s = store(null);
    const revoke = vi.fn();
    await endSession(sid, s, revoke);
    expect(revoke).not.toHaveBeenCalled();
    expect(s.delete).toHaveBeenCalledWith(sid);
  });

  it("does nothing without a well-formed cookie", async () => {
    const s = store(SESSION);
    await endSession(undefined, s, vi.fn());
    await endSession("bad", s, vi.fn());
    expect(s.find).not.toHaveBeenCalled();
    expect(s.delete).not.toHaveBeenCalled();
  });
});
