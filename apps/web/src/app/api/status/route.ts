// F10-AC13: asked by the start-up notice every 5 s. Public on purpose (no user data): it
// only tells whether the API and its database answer (API GET /health/ready).
import { connection } from "next/server";

import { apiReady } from "@/lib/api";
import { jsonNoStore } from "@/lib/as-caller";

export async function GET() {
  await connection();
  const ready = await apiReady();
  return jsonNoStore({ ready }, ready ? 200 : 503);
}
