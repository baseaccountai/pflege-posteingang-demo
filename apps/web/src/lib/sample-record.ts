// F10-AC14: the static sample record for /muster. The data comes from the seed
// (content/sample-record.json, written by `make sample-record`), never from the API.
//
// The seed sets its times relative to the day it runs ("3 days ago"); the file stores them
// as calendar days plus `generated_on`. Moving them to today keeps "neu" and "fällig" the
// same as in the live demo. Dates printed in the documents (document_date) stay.
import data from "@/content/sample-record.json";
import type { ResidentRecord } from "@/lib/residents";

export { sampleFileHref } from "@/lib/documents/file-href";

// Same list as RELATIVE in apps/api/scripts/build_sample_record.py.
const RELATIVE = new Set(["created_at", "confirmed_at", "discontinued_at", "approved_at", "done_at", "due_date"]);
const DAY_MS = 86_400_000;

const dayNumber = (isoDate: string) => Date.parse(`${isoDate}T00:00:00Z`) / DAY_MS;
const fromDayNumber = (day: number) => new Date(day * DAY_MS).toISOString().slice(0, 10);

function shift(value: unknown, days: number): unknown {
  if (Array.isArray(value)) return value.map((item) => shift(item, days));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        RELATIVE.has(key) && typeof item === "string" ? fromDayNumber(dayNumber(item) + days) : shift(item, days),
      ]),
    );
  }
  return value;
}

/** The sample record as it looks on `today` ("2026-10-28", the day in Berlin). */
export function sampleRecord(today: string): ResidentRecord {
  return shift(data.record, dayNumber(today) - dayNumber(data.generated_on)) as ResidentRecord;
}
