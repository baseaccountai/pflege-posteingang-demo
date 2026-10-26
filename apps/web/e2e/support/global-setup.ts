import postgres from "postgres";

import { ADMIN_DSN, BFF_PASSWORD, GATEWAY_PASSWORD, WB1_RESIDENT, WB2_RESIDENT } from "./env";

// The BFF logs in as bff_session, the API as api_gateway; their local passwords are set here
// (never in migrations). Two wards with one invented resident each.
export default async function globalSetup() {
  const admin = postgres(ADMIN_DSN, { max: 1, onnotice: () => {} });
  try {
    await admin.unsafe(`alter role bff_session password '${BFF_PASSWORD}'`);
    await admin.unsafe(`alter role api_gateway password '${GATEWAY_PASSWORD}'`);
    await admin`
      insert into public.wards (id, name) values ('wb1', 'WB 1'), ('wb2', 'WB 2')
      on conflict (id) do nothing`;
    await admin`
      insert into public.residents (id, ward_id, display_name)
      values (${WB1_RESIDENT.id}, 'wb1', ${WB1_RESIDENT.name}),
             (${WB2_RESIDENT.id}, 'wb2', ${WB2_RESIDENT.name})
      on conflict (id) do update set ward_id = excluded.ward_id,
                                     display_name = excluded.display_name`;
  } finally {
    await admin.end();
  }
}
