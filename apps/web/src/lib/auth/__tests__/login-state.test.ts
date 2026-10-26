// @vitest-environment node
// F01-AC5: state, nonce, PKCE verifier and role live in a short, encrypted, one-time cookie.
import { randomBytes } from "node:crypto";
import { describe, expect, it } from "vitest";

import { parseEncKey } from "../crypto";
import {
  LOGIN_COOKIE,
  loginCookieOptions,
  openLoginState,
  sealLoginState,
  type LoginState,
} from "../login-state";

const KEY = parseEncKey(randomBytes(32).toString("base64"));
const STATE: LoginState = { state: "s", nonce: "n", verifier: "v", role: "wb1" };
const NOW = Date.UTC(2026, 9, 26, 12);

describe("login state cookie", () => {
  it("is a short-lived __Host- cookie", () => {
    expect(LOGIN_COOKIE).toBe("__Host-pp_oidc");
    expect(loginCookieOptions()).toEqual({
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: 600,
    });
  });

  it("round-trips within 10 minutes", () => {
    const cookie = sealLoginState(STATE, KEY, NOW);
    expect(openLoginState(cookie, KEY, NOW + 599_000)).toEqual(STATE);
  });

  it("does not show its content in clear text", () => {
    const cookie = sealLoginState({ ...STATE, verifier: "secret-verifier" }, KEY, NOW);
    expect(Buffer.from(cookie, "base64url").toString("latin1")).not.toContain("secret-verifier");
  });

  it("expires after 10 minutes even if the browser keeps it", () => {
    expect(openLoginState(sealLoginState(STATE, KEY, NOW), KEY, NOW + 601_000)).toBeNull();
  });

  it.each([undefined, "", "garbage", "x".repeat(400)])("rejects %s", (value) => {
    expect(openLoginState(value, KEY, NOW)).toBeNull();
  });

  it("rejects a manipulated cookie", () => {
    const raw = Buffer.from(sealLoginState(STATE, KEY, NOW), "base64url");
    raw[raw.length - 1] ^= 0x01;
    expect(openLoginState(raw.toString("base64url"), KEY, NOW)).toBeNull();
  });

  it("cannot be replaced by a session token ciphertext (other context)", async () => {
    const { sealJson } = await import("../crypto");
    const foreign = sealJson({ ...STATE, exp: NOW + 1000 }, KEY, Buffer.alloc(32));
    expect(openLoginState(foreign.toString("base64url"), KEY, NOW)).toBeNull();
  });
});
