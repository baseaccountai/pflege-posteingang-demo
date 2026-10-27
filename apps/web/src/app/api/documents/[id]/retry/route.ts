// BFF: "Erneut versuchen" for a failed document (F02-AC8). Origin checked by proxy.ts.
import { connection, type NextRequest } from "next/server";

import { apiSend } from "@/lib/api";
import { bffRoute } from "@/lib/as-caller";

export async function POST(_request: NextRequest, ctx: RouteContext<"/api/documents/[id]/retry">) {
  await connection();
  const { id } = await ctx.params;
  return bffRoute((caller) =>
    apiSend(`/documents/${encodeURIComponent(id)}/retry`, caller, { method: "POST" }),
  );
}
