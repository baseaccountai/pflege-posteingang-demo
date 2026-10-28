// BFF: the original file for the review view (F03-AC4). Only the type found by the API's
// content check is used, the browser may not guess another one (nosniff).
import { connection, type NextRequest } from "next/server";

import { ApiUnauthorized, SessionEnded, apiFileForSession } from "@/lib/api";
import { isActive, jsonNoStore } from "@/lib/as-caller";
import { currentSession } from "@/lib/auth/current";

export async function GET(_request: NextRequest, ctx: RouteContext<"/api/documents/[id]/file">) {
  await connection();
  const { id } = await ctx.params;
  const state = await currentSession();
  if (state.kind !== "active") return jsonNoStore({ error_code: "session_expired" }, 401);
  try {
    // Checked again after the download: a role switch meanwhile drops the file (F01-AC13).
    const file = await apiFileForSession(
      `/documents/${encodeURIComponent(id)}/file`,
      { sid: state.sid, accessToken: state.session.tokens.access },
      isActive,
    );
    if (!file) return jsonNoStore({ error_code: "not_found" }, 404);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.contentType,
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    if (error instanceof ApiUnauthorized || error instanceof SessionEnded) {
      return jsonNoStore({ error_code: "session_expired" }, 401);
    }
    throw error;
  }
}
