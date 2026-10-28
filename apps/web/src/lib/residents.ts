// Residents in the name of the signed-in user. Which rows exist is decided by RLS in the
// database (via the API), not here.
import type { ProvenanceData } from "@/components/provenance";

import { getAsCaller, type PageResult } from "./as-caller";

export type Resident = {
  id: string;
  ward_id: string;
  ward_name: string;
  display_name: string;
  room: string | null;
};

/** F04-AC1, AC2: an entry of the resident list. */
export type ResidentSummary = Resident & {
  has_new: boolean;
  open_follow_ups: number;
  overdue_follow_ups: number;
};

export type Dosage = Record<"morgens" | "mittags" | "abends" | "nachts", string>;
export type MedicationSide = { name: string; strength: string | null; dosage: Dosage; hint?: string | null };

export type MedicationEvent = {
  kind: "new" | "changed" | "discontinued";
  before: MedicationSide | null;
  after: MedicationSide | null;
  created_at: string;
  provenance: ProvenanceData;
};

export type RecordMedication = {
  id: string;
  name: string;
  strength: string | null;
  dosage: Dosage;
  hint?: string | null; // "bei Bedarf" (F04-AC4)
  status: "active" | "discontinued";
  marker?: "new" | "changed" | null;
  previous?: MedicationSide | null;
  discontinued_at?: string;
  provenance: ProvenanceData | null;
  events: MedicationEvent[];
};

export type RecordFollowUp = {
  id: string;
  title: string;
  due_date: string | null;
  status: "open" | "done";
  overdue: boolean;
  done_by_name: string | null;
  done_at: string | null;
  provenance: ProvenanceData;
};

export type ResidentRecord = {
  resident: Resident;
  medications: { active: RecordMedication[]; discontinued: RecordMedication[] };
  diagnoses: { id: string; text: string; provenance: ProvenanceData }[];
  follow_ups: RecordFollowUp[];
  documents: {
    id: string;
    doc_type: string | null;
    document_date: string | null;
    approved_by_name: string | null;
    approved_at: string | null;
  }[];
};

/** F04-AC1: the residents of the own wards; status 503 while the API starts (F10-AC13). */
export async function listResidents(): Promise<PageResult<ResidentSummary[]>> {
  return getAsCaller<ResidentSummary[]>("/residents");
}

/**
 * F04: the whole record; 404 for foreign, unknown and malformed ids alike (F04-AC9),
 * 503 while the API starts (F10-AC13).
 */
export async function getRecord(id: string): Promise<PageResult<ResidentRecord>> {
  return getAsCaller<ResidentRecord>(`/residents/${encodeURIComponent(id)}/record`);
}
