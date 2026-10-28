// BFF: make an approved document searchable again after a failed indexing (F05-AC1a).
// Origin checked by proxy.ts.
import { connection, type NextRequest } from "next/server";

import { apiSend } from "@/lib/api";
import { bffRoute } from "@/lib/as-caller";

export async function POST(_request: NextRequest, ctx: RouteContext<"/api/documents/[id]/reindex">) {
  await connection();
  const { id } = await ctx.params;
  return bffRoute((caller) =>
    apiSend(`/documents/${encodeURIComponent(id)}/reindex`, caller, { method: "POST" }),
  );
}
