// Prepares the local database for the end-to-end tests, run right before the API starts
// (Playwright starts its web servers before globalSetup, and the API connects at startup).
// Sets the local-only passwords of the login roles and seeds two invented residents.
// All values come from E2E_DB_PREP (JSON), built in e2e/support/env.ts.
import postgres from "postgres";

const prep = JSON.parse(process.env.E2E_DB_PREP ?? "{}");
const admin = postgres(prep.adminDsn, { max: 1, onnotice: () => {} });
try {
  for (const [role, password] of Object.entries(prep.passwords)) {
    await admin.unsafe(`alter role ${role} password '${password}'`);
  }
  await admin`
    insert into public.wards (id, name) values ('wb1', 'WB 1'), ('wb2', 'WB 2')
    on conflict (id) do nothing`;
  // Test database only: quota counters start at zero, so repeated runs never hit a limit.
  await admin`truncate public.usage_counters`;
  // One run uploads more documents (desktop + mobile) than the injection check's daily
  // limit of 20 allows; raised for the run, set back in global-teardown.ts (F07).
  await admin`update public.quota_limits set max_count = 500 where kind = 'guard_document'`;
  for (const resident of prep.residents) {
    await admin`
      insert into public.residents (id, ward_id, display_name)
      values (${resident.id}, ${resident.ward}, ${resident.name})
      on conflict (id) do update set ward_id = excluded.ward_id,
                                     display_name = excluded.display_name`;
  }
} finally {
  await admin.end();
}
