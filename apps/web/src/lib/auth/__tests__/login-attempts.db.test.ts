// @vitest-environment node
// F01-AC5: a login attempt can be completed exactly once, also with a stolen login cookie.
import { createHash } from "node:crypto";
import postgres from "postgres";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";

import { LoginAttempts } from "../login-attempts";

const ADMIN_DSN =
  process.env.TEST_ADMIN_DATABASE_URL ?? "postgresql://postgres:postgres@127.0.0.1:56322/postgres";
// Local-only password, set below; never used outside tests.
const BFF_PASSWORD = "bff_session_local_test";
const BFF_DSN = `postgresql://bff_session:${BFF_PASSWORD}@127.0.0.1:56322/postgres`;

const admin = postgres(ADMIN_DSN, { max: 1, onnotice: () => {} });
const sql = postgres(BFF_DSN, { max: 8, prepare: false });
const attempts = new LoginAttempts(sql);

beforeAll(async () => {
  await admin.unsafe(`alter role bff_session password '${BFF_PASSWORD}'`);
});

beforeEach(async () => {
  await admin`truncate bff.login_attempts`;
});

afterAll(async () => {
  await sql.end();
  await admin.end();
});

describe("LoginAttempts", () => {
  it("consumes a started attempt exactly once", async () => {
    await attempts.begin("state-1");
    expect(await attempts.consume("state-1")).toBe(true);
    expect(await attempts.consume("state-1")).toBe(false);
  });

  it("rejects an unknown state", async () => {
    expect(await attempts.consume("never-started")).toBe(false);
  });

  it("rejects an attempt older than 10 minutes", async () => {
    await attempts.begin("state-old");
    await admin`update bff.login_attempts set expires_at = now() - interval '1 second'`;
    expect(await attempts.consume("state-old")).toBe(false);
  });

  it("lets only one of several parallel callbacks through", async () => {
    await attempts.begin("state-race");
    const results = await Promise.all(Array.from({ length: 8 }, () => attempts.consume("state-race")));
    expect(results.filter(Boolean)).toHaveLength(1);
  });

  it("stores only a hash of the state and removes expired attempts", async () => {
    await attempts.begin("state-a");
    await admin`update bff.login_attempts set expires_at = now() - interval '1 second'`;
    await attempts.begin("state-b");
    const rows = await admin<{ state_hash: Buffer }[]>`select state_hash from bff.login_attempts`;
    expect(rows.map((r) => Buffer.from(r.state_hash))).toEqual([
      createHash("sha256").update("state-b").digest(),
    ]);
  });
});
