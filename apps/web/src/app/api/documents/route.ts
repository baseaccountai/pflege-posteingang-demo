// BFF for the inbox: GET lists the caller's documents (polling), POST uploads one (F02).
// Origin is checked by proxy.ts for the POST (F01-AC15); tokens stay on the server.
import { connection, type NextRequest } from "next/server";

import { apiGetForSession, apiSend } from "@/lib/api";
import { bffRoute, isActive, jsonNoStore } from "@/lib/as-caller";

export async function GET() {
  await connection();
  return bffRoute((caller) => apiGetForSession("/documents", caller, isActive));
}

export async function POST(request: NextRequest) {
  await connection();
  let incoming: FormData;
  try {
    incoming = await request.formData();
  } catch {
    return jsonNoStore({ error_code: "bad_request", message: "Keine Datei erhalten." }, 400);
  }
  const file = incoming.get("file");
  if (!(file instanceof File)) {
    return jsonNoStore({ error_code: "bad_request", message: "Keine Datei erhalten." }, 400);
  }
  // Only the two known fields go on to the API.
  const body = new FormData();
  body.set("file", file, file.name);
  const ward = incoming.get("ward_id");
  if (typeof ward === "string" && ward) body.set("ward_id", ward);
  return bffRoute((caller) => apiSend("/documents", caller, { method: "POST", body }));
}
