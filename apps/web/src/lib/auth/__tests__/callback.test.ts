// @vitest-environment node
// F01-AC5: the code is only redeemed if the server-side login attempt is still open.
import { describe, expect, it, vi } from "vitest";

import { completeLogin } from "../callback";
import type { LoginState } from "../login-state";
import type { NewSession } from "../session-store";

const STATE: LoginState = { state: "s", nonce: "n", verifier: "v", role: "wb1" };
const SESSION = { sub: "u" } as NewSession;

function deps(consumed: boolean) {
  return {
    consume: vi.fn().mockResolvedValue(consumed),
    finish: vi.fn().mockResolvedValue(SESSION),
    create: vi.fn().mockResolvedValue("sid-1"),
  };
}

describe("completeLogin", () => {
  it("redeems the code and creates the session for an open attempt", async () => {
    const d = deps(true);
    expect(await completeLogin(STATE, d)).toBe("sid-1");
    expect(d.consume).toHaveBeenCalledWith("s");
    expect(d.create).toHaveBeenCalledWith(SESSION);
  });

  it("never contacts the IdP for an attempt that was already used (replay)", async () => {
    const d = deps(false);
    expect(await completeLogin(STATE, d)).toBeNull();
    expect(d.finish).not.toHaveBeenCalled();
    expect(d.create).not.toHaveBeenCalled();
  });

  it("returns null without a login state", async () => {
    const d = deps(true);
    expect(await completeLogin(null, d)).toBeNull();
    expect(d.consume).not.toHaveBeenCalled();
  });

  it("returns null if the IdP check fails", async () => {
    const d = { ...deps(true), finish: vi.fn().mockRejectedValue(new Error("bad nonce")) };
    expect(await completeLogin(STATE, d)).toBeNull();
    expect(d.create).not.toHaveBeenCalled();
  });
});
