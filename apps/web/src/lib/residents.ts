// Residents in the name of the signed-in user. Which rows exist is decided by RLS in the
// database (via the API), not here.
import { getAsCaller } from "./as-caller";

export type Resident = { id: string; ward_id: string; display_name: string; room: string | null };

export async function listResidents(): Promise<Resident[]> {
  return (await getAsCaller<Resident[]>("/residents")).data ?? [];
}

/** null for foreign, unknown and malformed ids alike (F01-AC12). */
export async function getResident(id: string): Promise<Resident | null> {
  return (await getAsCaller<Resident>(`/residents/${encodeURIComponent(id)}`)).data;
}
