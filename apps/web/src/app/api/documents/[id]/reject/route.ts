// BFF: review step "reject" of a document (F03). Origin checked by proxy.ts (F01-AC15).
import { connection, type NextRequest } from "next/server";

import { apiSend } from "@/lib/api";
import { bffRoute } from "@/lib/as-caller";

export async function POST(request: NextRequest, ctx: RouteContext<"/api/documents/[id]/reject">) {
  await connection();
  const { id } = await ctx.params;
  const body = undefined;
  return bffRoute((caller) =>
    apiSend(`/documents/${encodeURIComponent(id)}/reject`, caller, {
      method: "POST",
      body,
      headers: { "content-type": "application/json" },
    }),
  );
}
