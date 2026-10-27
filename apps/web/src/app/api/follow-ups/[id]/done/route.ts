// BFF: mark a follow-up done (F04-AC8). Origin checked by proxy.ts (F01-AC15).
import { connection, type NextRequest } from "next/server";

import { apiSend } from "@/lib/api";
import { bffRoute } from "@/lib/as-caller";

export async function POST(_request: NextRequest, ctx: RouteContext<"/api/follow-ups/[id]/done">) {
  await connection();
  const { id } = await ctx.params;
  return bffRoute((caller) =>
    apiSend(`/follow-ups/${encodeURIComponent(id)}/done`, caller, { method: "POST" }),
  );
}
