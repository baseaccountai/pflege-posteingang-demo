// @vitest-environment node
// F01-AC3: random session id (>= 256 bit), only its SHA-256 is stored, tokens AES-256-GCM.
import { createHash, randomBytes } from "node:crypto";
import { describe, expect, it } from "vitest";

import {
  hashSessionId,
  newSessionId,
  openTokens,
  parseEncKey,
  sealTokens,
  type TokenSet,
} from "../session-store";

const KEY = parseEncKey(randomBytes(32).toString("base64"));
const ROW = hashSessionId(newSessionId());
const TOKENS: TokenSet = { access: "a.b.c", refresh: "r-123", id: "i.d.t" };

describe("session id", () => {
  it("has at least 256 bits of randomness, url-safe", () => {
    const sid = newSessionId();
    expect(sid).toMatch(/^[A-Za-z0-9_-]{43,}$/);
    expect(Buffer.from(sid, "base64url").length).toBeGreaterThanOrEqual(32);
    expect(newSessionId()).not.toBe(sid);
  });

  it("is stored only as its SHA-256", () => {
    const sid = newSessionId();
    expect(hashSessionId(sid)).toEqual(createHash("sha256").update(sid).digest());
  });
});

describe("token encryption", () => {
  it("round-trips the token set", () => {
    expect(openTokens(sealTokens(TOKENS, KEY, ROW), KEY, ROW)).toEqual(TOKENS);
  });

  it("does not contain any token in clear text", () => {
    const sealed = sealTokens(TOKENS, KEY, ROW).toString("latin1");
    for (const token of Object.values(TOKENS)) expect(sealed).not.toContain(token);
  });

  it("uses a fresh IV every time", () => {
    expect(sealTokens(TOKENS, KEY, ROW)).not.toEqual(sealTokens(TOKENS, KEY, ROW));
  });

  it("detects a manipulated ciphertext", () => {
    const sealed = sealTokens(TOKENS, KEY, ROW);
    sealed[sealed.length - 20] ^= 0x01;
    expect(() => openTokens(sealed, KEY, ROW)).toThrow();
  });

  it("rejects another key", () => {
    const other = parseEncKey(randomBytes(32).toString("base64"));
    expect(() => openTokens(sealTokens(TOKENS, KEY, ROW), other, ROW)).toThrow();
  });

  it("binds the ciphertext to its session row", () => {
    // Copying tokens_enc into another session's row must not work.
    const otherRow = hashSessionId(newSessionId());
    expect(() => openTokens(sealTokens(TOKENS, KEY, ROW), KEY, otherRow)).toThrow();
  });
});

describe("SESSION_ENC_KEY", () => {
  it.each([undefined, "", "c2hvcnQ=", randomBytes(31).toString("base64")])(
    "refuses %s (must be 32 bytes, base64)",
    (value) => {
      expect(() => parseEncKey(value)).toThrow(/SESSION_ENC_KEY/);
    },
  );
});
