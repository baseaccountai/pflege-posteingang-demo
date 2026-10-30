// BFF for the audit log (F12-AC7): "Ältere laden" and the filters. Only the PDL; the API
// refuses everyone else as well. Only known parameters go on to the API.
import { connection, type NextRequest } from "next/server";

import { apiGetForSession } from "@/lib/api";
import { bffRoute, isActive, jsonNoStore } from "@/lib/as-caller";
import { auditQuery } from "@/lib/audit";
import { currentSession } from "@/lib/auth/current";

export async function GET(request: NextRequest) {
  await connection();
  const state = await currentSession();
  if (state.kind === "active" && state.session.appRole !== "pdl") {
    return jsonNoStore({ error_code: "pdl_only", message: "Das Protokoll sieht nur die Pflegedienstleitung." }, 403);
  }
  const params = request.nextUrl.searchParams;
  const before = params.get("before");
  const query = auditQuery({
    before: before && /^\d{1,18}$/.test(before) ? Number(before) : undefined,
    agentOnly: params.get("agent_only") === "true",
    blockedOnly: params.get("blocked_only") === "true",
  });
  return bffRoute((caller) => apiGetForSession(`/audit${query}`, caller, isActive));
}
