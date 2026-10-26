import postgres from "postgres";

import { ADMIN_DSN, BFF_PASSWORD } from "./env";

// The BFF logs in as bff_session; its local password is set here (never in migrations).
export default async function globalSetup() {
  const admin = postgres(ADMIN_DSN, { max: 1, onnotice: () => {} });
  try {
    await admin.unsafe(`alter role bff_session password '${BFF_PASSWORD}'`);
  } finally {
    await admin.end();
  }
}
