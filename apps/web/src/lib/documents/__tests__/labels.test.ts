// F02-AC7, AC8, AC13: status badges and messages per error code.
import { describe, expect, it } from "vitest";

import { STATUS_LABELS, errorMessage, isPending } from "../labels";

describe("status labels", () => {
  it("names every status like the spec", () => {
    expect(STATUS_LABELS).toEqual({
      uploaded: "wartet",
      processing: "in Bearbeitung",
      extracting: "in Bearbeitung",
      ready_for_review: "bereit zur Prüfung",
      approved: "freigegeben",
      rejected: "verworfen",
      unreadable: "nicht lesbar",
      failed: "Fehler",
    });
  });

  it("treats only running steps as pending (polling)", () => {
    expect(["uploaded", "processing", "extracting"].every(isPending)).toBe(true);
    expect(["ready_for_review", "failed", "unreadable", "approved"].some(isPending)).toBe(false);
  });
});

describe("errorMessage", () => {
  it("uses the exact texts for unreadable documents (AC7)", () => {
    expect(errorMessage("unreadable_text")).toBe(
      "Dokument nicht lesbar – bitte neu fotografieren (gerade, hell, ganze Seite)",
    );
    expect(errorMessage("not_care_document")).toBe("Kein Pflegedokument erkannt");
  });

  it("says why a document was not sent to the AI (F06-AC10)", () => {
    expect(errorMessage("pseudonymization_failed")).toBe(
      "Aus Datenschutzgründen nicht an die KI gesendet – bitte erneut versuchen.",
    );
  });

  it("has a message for every processing error (AC8)", () => {
    for (const code of ["ocr_unavailable", "llm_unavailable", "quota_exceeded", "timeout"]) {
      expect(errorMessage(code)).toMatch(/\S{10}/);
    }
    expect(errorMessage("quota_exceeded")).toBe(
      "Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter.",
    );
  });

  it("returns nothing for no code and a generic text for an unknown one", () => {
    expect(errorMessage(null)).toBeNull();
    expect(errorMessage("something_new")).toBe("Unbekannter Fehler – bitte erneut versuchen.");
  });
});
