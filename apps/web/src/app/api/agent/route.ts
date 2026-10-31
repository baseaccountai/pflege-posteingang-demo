// BFF for the agent (F08). Origin checked by proxy.ts. The nurse's token goes to the API,
// which exchanges it for the agent's token - neither token reaches the browser. The session
// is checked again after the answer, like for questions (F05-AC11).
import { connection, type NextRequest } from "next/server";

import { apiSendForSession } from "@/lib/api";
import { bffRoute, isActive, jsonNoStore } from "@/lib/as-caller";

export async function POST(request: NextRequest) {
  await connection();
  const input = await request.json().catch(() => null);
  const task = typeof input?.task === "string" ? input.task : "";
  const resident = typeof input?.resident_id === "string" && input.resident_id ? input.resident_id : undefined;
  if (!task.trim() || task.length > 500) {
    return jsonNoStore({ error_code: "bad_request", message: "Bitte einen Auftrag mit höchstens 500 Zeichen." }, 400);
  }
  // Only the two known fields go on to the API.
  const body = JSON.stringify(resident ? { task, resident_id: resident } : { task });
  return bffRoute((caller) =>
    apiSendForSession(
      "/agent",
      caller,
      { method: "POST", body, headers: { "content-type": "application/json" } },
      isActive,
    ),
  );
}
