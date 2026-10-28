// BFF for questions (F05). Origin checked by proxy.ts. The session is checked again after
// the answer: an answer to a question of the previous role is never delivered (F05-AC11).
import { connection, type NextRequest } from "next/server";

import { apiSendForSession } from "@/lib/api";
import { bffRoute, isActive, jsonNoStore } from "@/lib/as-caller";

export async function POST(request: NextRequest) {
  await connection();
  const input = await request.json().catch(() => null);
  const question = typeof input?.question === "string" ? input.question : "";
  const resident = typeof input?.resident_id === "string" && input.resident_id ? input.resident_id : undefined;
  if (!question.trim() || question.length > 500) {
    return jsonNoStore({ error_code: "bad_request", message: "Bitte eine Frage mit höchstens 500 Zeichen." }, 400);
  }
  // Only the two known fields go on to the API.
  const body = JSON.stringify(resident ? { question, resident_id: resident } : { question });
  return bffRoute((caller) =>
    apiSendForSession(
      "/questions",
      caller,
      { method: "POST", body, headers: { "content-type": "application/json" } },
      isActive,
    ),
  );
}
