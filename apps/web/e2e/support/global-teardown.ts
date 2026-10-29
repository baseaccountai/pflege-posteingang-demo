import { execFileSync } from "node:child_process";

import postgres from "postgres";

import { DB_PREP, MOCK_OIDC_CONTAINER } from "./env";

// Playwright ends only the docker client; the test OIDC container is removed here.
// The injection check's daily limit, raised for the run in prepare-db.mjs, goes back to
// the value of supabase/migrations/20261029020000_f07_guard_quota.sql.
export default async function globalTeardown() {
  try {
    execFileSync("docker", ["rm", "-f", MOCK_OIDC_CONTAINER], { stdio: "ignore" });
  } catch {
    // already gone
  }
  const admin = postgres(DB_PREP.adminDsn, { max: 1, onnotice: () => {} });
  try {
    await admin`update public.quota_limits set max_count = 20 where kind = 'guard_document'`;
  } finally {
    await admin.end();
  }
}
