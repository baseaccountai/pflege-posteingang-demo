// @vitest-environment node
// F01-AC3, F01-AC21 against the local Supabase database (make db-start), as role bff_session.
import { createHash, randomBytes } from "node:crypto";
import postgres from "postgres";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionStore, parseEncKey, type TokenSet } from "../session-store";

const ADMIN_DSN =
  process.env.TEST_ADMIN_DATABASE_URL ?? "postgresql://postgres:postgres@127.0.0.1:56322/postgres";
// Local-only password, set below; never used outside tests.
const BFF_PASSWORD = "bff_session_local_test";
const BFF_DSN = `postgresql://bff_session:${BFF_PASSWORD}@127.0.0.1:56322/postgres`;

const admin = postgres(ADMIN_DSN, { max: 1, onnotice: () => {} });
const sql = postgres(BFF_DSN, { max: 4, prepare: false });
const KEY = parseEncKey(randomBytes(32).toString("base64"));
const store = new SessionStore(sql, KEY);

const TOKENS: TokenSet = { access: "access-1", refresh: "refresh-1", id: "id-1" };
const inOneHour = () => new Date(Date.now() + 3600_000);

function newSession(tokens: TokenSet = TOKENS, accessExpiresAt = inOneHour()) {
  return store.create({
    sub: "user-1",
    appRole: "nurse_wb1",
    displayName: "Pflegekraft WB1",
    tokens,
    accessExpiresAt,
  });
}

const sha256 = (sid: string) => createHash("sha256").update(sid).digest();

beforeAll(async () => {
  await admin.unsafe(`alter role bff_session password '${BFF_PASSWORD}'`);
});

beforeEach(async () => {
  await admin`truncate bff.sessions`;
});

afterAll(async () => {
  await sql.end();
  await admin.end();
});

describe("create", () => {
  it("stores only the hash of the session id and encrypted tokens", async () => {
    const sid = await newSession();
    const rows = await admin`select * from bff.sessions`;
    expect(rows).toHaveLength(1);
    expect(rows[0].id_hash).toEqual(sha256(sid));
    const dump = JSON.stringify(rows[0]) + Buffer.from(rows[0].tokens_enc).toString("latin1");
    for (const secret of [sid, ...Object.values(TOKENS)]) expect(dump).not.toContain(secret);
  });

  it("ends the session after at most 8 hours", async () => {
    await newSession();
    const [row] = await admin`select expires_at - created_at as lifetime from bff.sessions`;
    expect(row.lifetime).toBe("08:00:00");
  });
});

describe("find", () => {
  it("returns the session with decrypted tokens", async () => {
    const session = await store.find(await newSession());
    expect(session).toMatchObject({ sub: "user-1", appRole: "nurse_wb1", tokens: TOKENS });
  });

  it("returns null for an unknown, expired or revoked session", async () => {
    expect(await store.find("unknown")).toBeNull();
    const expired = await newSession();
    await admin`update bff.sessions set expires_at = now() - interval '1 second'
                where id_hash = ${sha256(expired)}`;
    expect(await store.find(expired)).toBeNull();
    const revoked = await newSession();
    await store.revoke(revoked);
    expect(await store.find(revoked)).toBeNull();
  });

  it("returns null if the row's tokens were swapped from another session", async () => {
    const victim = await newSession();
    const attacker = await newSession({ access: "x", refresh: null, id: null });
    await admin`update bff.sessions set tokens_enc =
                  (select tokens_enc from bff.sessions where id_hash = ${sha256(victim)})
                where id_hash = ${sha256(attacker)}`;
    expect(await store.find(attacker)).toBeNull();
  });
});

describe("delete", () => {
  it("removes the row (logout)", async () => {
    const sid = await newSession();
    await store.delete(sid);
    expect(await admin`select 1 from bff.sessions`).toHaveLength(0);
  });
});

describe("refreshIfDue", () => {
  const dueSoon = () => new Date(Date.now() + 10_000); // inside the 60 s margin
  const refreshed = { tokens: { access: "access-2" }, accessExpiresAt: inOneHour() };

  it("does not refresh while the access token is still valid", async () => {
    const refresh = vi.fn();
    const session = await store.refreshIfDue(await newSession(), refresh);
    expect(refresh).not.toHaveBeenCalled();
    expect(session?.tokens.access).toBe("access-1");
  });

  it("refreshes a due access token and keeps the absolute 8 h end", async () => {
    const sid = await newSession(TOKENS, dueSoon());
    const [before] = await admin`select expires_at from bff.sessions`;
    const refresh = vi.fn().mockResolvedValue(refreshed);
    const session = await store.refreshIfDue(sid, refresh);
    expect(refresh).toHaveBeenCalledWith("refresh-1");
    // The IdP may omit a new refresh/id token: the old ones are kept.
    expect(session?.tokens).toEqual({ access: "access-2", refresh: "refresh-1", id: "id-1" });
    expect((await store.find(sid))?.tokens.access).toBe("access-2");
    const [after] = await admin`select expires_at from bff.sessions`;
    expect(after.expires_at).toEqual(before.expires_at);
  });

  it("refreshes only once for parallel requests", async () => {
    const sid = await newSession(TOKENS, dueSoon());
    const refresh = vi.fn(async () => {
      await new Promise((resolve) => setTimeout(resolve, 200));
      return refreshed;
    });
    const results = await Promise.all([1, 2, 3].map(() => store.refreshIfDue(sid, refresh)));
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(results.map((s) => s?.tokens.access)).toEqual(["access-2", "access-2", "access-2"]);
  });

  it("revokes the session if the refresh fails", async () => {
    const sid = await newSession(TOKENS, dueSoon());
    const refresh = vi.fn().mockRejectedValue(new Error("invalid_grant"));
    expect(await store.refreshIfDue(sid, refresh)).toBeNull();
    const [row] = await admin`select revoked_at from bff.sessions`;
    expect(row.revoked_at).not.toBeNull();
  });

  it("revokes the session if there is no refresh token", async () => {
    const sid = await newSession({ access: "a", refresh: null, id: null }, dueSoon());
    const refresh = vi.fn();
    expect(await store.refreshIfDue(sid, refresh)).toBeNull();
    expect(refresh).not.toHaveBeenCalled();
    expect(await store.find(sid)).toBeNull();
  });

  it("returns null for an expired session without refreshing", async () => {
    const sid = await newSession(TOKENS, dueSoon());
    await admin`update bff.sessions set expires_at = now() - interval '1 second'`;
    const refresh = vi.fn();
    expect(await store.refreshIfDue(sid, refresh)).toBeNull();
    expect(refresh).not.toHaveBeenCalled();
  });
});

describe("role bff_session", () => {
  it("cannot read application data", async () => {
    await expect(sql`select * from public.residents`).rejects.toThrow(/permission denied/);
  });
});
