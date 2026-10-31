// BFF: confirm a proposal of the agent - the API sets it to confirmed as the nurse, then
// lets the agent write the follow-up (F08-AC6). Origin checked by proxy.ts.
import { connection, type NextRequest } from "next/server";

import { apiSend } from "@/lib/api";
import { bffRoute } from "@/lib/as-caller";

export async function POST(_request: NextRequest, ctx: RouteContext<"/api/agent/proposals/[id]/confirm">) {
  await connection();
  const { id } = await ctx.params;
  return bffRoute((caller) =>
    apiSend(`/agent/proposals/${encodeURIComponent(id)}/confirm`, caller, { method: "POST" }),
  );
}
