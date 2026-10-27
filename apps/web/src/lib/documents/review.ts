// Types and helpers of the review view (F03). The suggestion comes from the API: every
// field has value (null if its source was not found), proposed, evidence, evidence_found.

export type Field<T> = { value: T | null; proposed: T | null; evidence: string | null; evidence_found: boolean };
export type Dosage = { morgens: string | null; mittags: string | null; abends: string | null; nachts: string | null };
export type MedicationValue = { name: string; strength: string | null; dosage: Dosage; hint: string | null };
export type FollowUpValue = { title: string; due_date: string | null };

export type Suggestion = {
  doc_type: Field<string>;
  document_date: Field<string>;
  issuer: Field<string>;
  resident_name: Field<string>;
  diagnoses: Field<string>[];
  medications: Field<MedicationValue>[];
  follow_ups: Field<FollowUpValue>[];
};

export type MedicationChange = {
  kind: string;
  name: string;
  medication_id: string | null;
  before: unknown;
  after: unknown;
};

export const CHANGE_LABELS: Record<string, string> = {
  new: "neu",
  changed: "geändert",
  unchanged: "unverändert",
  discontinued: "abgesetzt",
};

export const SLOTS = ["morgens", "mittags", "abends", "nachts"] as const;

/** Short text of a value that could not be prefilled ("nicht im Dokument gefunden"). */
export function describe(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  const v = value as Partial<MedicationValue & FollowUpValue>;
  return [v.name ?? v.title, v.strength ?? v.due_date].filter(Boolean).join(" ");
}

export function foundValues<T>(fields: Field<T>[] | undefined): T[] {
  return (fields ?? []).filter((f) => f.evidence_found && f.value != null).map((f) => f.value as T);
}

export function missingValues(suggestion: Suggestion | null): string[] {
  if (!suggestion) return [];
  const single = [suggestion.doc_type, suggestion.document_date, suggestion.issuer, suggestion.resident_name];
  const lists = [...suggestion.diagnoses, ...suggestion.medications, ...suggestion.follow_ups] as Field<unknown>[];
  return [...single, ...lists]
    .filter((f) => f && !f.evidence_found && f.proposed != null)
    .map((f) => describe(f.proposed));
}
