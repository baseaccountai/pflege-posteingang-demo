// Residents in the name of the signed-in user. Which rows exist is decided by RLS in the
// database (via the API), not here.
import { redirect } from "next/navigation";

import { ApiUnauthorized, SessionEnded, apiGetForSession, type ApiResult } from "./api";
import { EXPIRED_PATH, requireSession } from "./auth/current";
import { sessionStore } from "./auth/session";

export type Resident = { id: string; ward_id: string; display_name: string; room: string | null };

async function asCaller<T>(path: string): Promise<ApiResult<T>> {
  const { sid, session } = await requireSession();
  let result: ApiResult<T>;
  try {
    // Checked again after the call: a late answer of an ended session is never shown.
    const isActive = async (id: string) => (await sessionStore().find(id)) !== null;
    result = await apiGetForSession<T>(path, { sid, accessToken: session.tokens.access }, isActive);
  } catch (error) {
    if (error instanceof ApiUnauthorized || error instanceof SessionEnded) redirect(EXPIRED_PATH);
    throw error;
  }
  return result;
}

export async function listResidents(): Promise<Resident[]> {
  return (await asCaller<Resident[]>("/residents")).data ?? [];
}

/** null for foreign, unknown and malformed ids alike (F01-AC12). */
export async function getResident(id: string): Promise<Resident | null> {
  return (await asCaller<Resident>(`/residents/${encodeURIComponent(id)}`)).data;
}
