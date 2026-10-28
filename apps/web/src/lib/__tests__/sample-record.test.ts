// F10-AC14: the static sample record comes from the seed file; its seed-relative days are
// moved to today, so it looks like the live demo after a nightly reset.
import { describe, expect, it } from "vitest";

import data from "@/content/sample-record.json";
import { sampleFileHref, sampleRecord } from "@/lib/sample-record";

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

describe("sampleRecord", () => {
  it("is the generated file on the day it was generated", () => {
    expect(sampleRecord(data.generated_on)).toEqual(data.record);
  });

  it("moves the seed-relative days to today", () => {
    const today = addDays(data.generated_on, 40); // across a month end
    const record = sampleRecord(today);
    const original = data.record;
    record.medications.active.forEach((med, i) => {
      const before = original.medications.active[i];
      expect(med.provenance?.confirmed_at).toBe(addDays(before.provenance.confirmed_at, 40));
      med.events.forEach((event, j) => {
        expect(event.created_at).toBe(addDays(before.events[j].created_at, 40));
      });
    });
    record.follow_ups.forEach((entry, i) => {
      const before = original.follow_ups[i];
      expect(entry.due_date).toBe(before.due_date && addDays(before.due_date, 40));
      expect(entry.done_at).toBe(before.done_at && addDays(before.done_at, 40));
    });
    record.documents.forEach((document, i) => {
      expect(document.approved_at).toBe(addDays(original.documents[i].approved_at!, 40));
    });
  });

  it("keeps the dates printed in the documents", () => {
    const record = sampleRecord(addDays(data.generated_on, 40));
    expect(record.documents.map((d) => d.document_date)).toEqual(
      data.record.documents.map((d) => d.document_date),
    );
    expect(record.diagnoses[0].provenance.document_date).toBe(
      data.record.diagnoses[0].provenance.document_date,
    );
  });
});

describe("sampleFileHref", () => {
  it("points to the static copy of the original", () => {
    expect(sampleFileHref("5eed0000-0000-0000-0000-000000000002")).toBe(
      "/muster/5eed0000-0000-0000-0000-000000000002.pdf",
    );
  });
});
