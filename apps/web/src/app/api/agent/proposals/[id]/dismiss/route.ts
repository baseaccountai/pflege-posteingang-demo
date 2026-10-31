// BFF: dismiss a proposal of the agent (F08-AC5); nothing is written into the record. Origin checked by proxy.ts.
import { connection, type NextRequest } from "next/server";

import { apiSend } from "@/lib/api";
import { bffRoute } from "@/lib/as-caller";

export async function POST(_request: NextRequest, ctx: RouteContext<"/api/agent/proposals/[id]/dismiss">) {
  await connection();
  const { id } = await ctx.params;
  return bffRoute((caller) =>
    apiSend(`/agent/proposals/${encodeURIComponent(id)}/dismiss`, caller, { method: "POST" }),
  );
}
