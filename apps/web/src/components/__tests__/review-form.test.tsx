// F03-AC2 to AC7, AC12: review form - prefilled only with found values, resident must be
// confirmed, changing the resident resets the confirmation and recomputes the comparison.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewForm, type ReviewProps } from "@/components/review-form";
import type { Field, Suggestion } from "@/lib/documents/review";

const found = <T,>(value: T): Field<T> => ({ value, proposed: value, evidence: "x", evidence_found: true });
const missing = <T,>(proposed: T): Field<T> => ({ value: null, proposed, evidence: "y", evidence_found: false });
const DOSE = { morgens: "1", mittags: "0", abends: "0", nachts: "0" };

const SUGGESTION: Suggestion = {
  doc_type: found("medikationsplan"),
  document_date: found("2026-10-22"),
  issuer: found("Hausarztpraxis Dr. Ipsum"),
  resident_name: found("Hr. Muster-Bauer"),
  diagnoses: [found("Herzinsuffizienz"), missing("Asthma")],
  medications: [found({ name: "Torasemid", strength: "10 mg", dosage: DOSE, hint: null }), missing({ name: "Erfundol", strength: "50 mg", dosage: DOSE, hint: null })],
  follow_ups: [],
};

function props(over: Partial<ReviewProps> = {}): ReviewProps {
  return {
    documentId: "d1",
    model: "mistral-small-latest",
    suggestion: SUGGESTION,
    residents: [
      { id: "r1", display_name: "Hr. Muster-Bauer" },
      { id: "r2", display_name: "Hr. Probe" },
    ],
    candidate: "r1",
    changes: [{ kind: "new", name: "Torasemid", medication_id: null, before: null, after: null }],
    diffHash: "h1",
    ...over,
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ReviewForm", () => {
  it("names the model and asks to check every field (AC12)", () => {
    render(<ReviewForm {...props()} />);
    expect(screen.getByText("KI-Vorschlag – bitte jedes Feld prüfen")).toBeInTheDocument();
    expect(screen.getByText(/mistral-small-latest/)).toBeInTheDocument();
  });

  it("prefills only values with a source and marks the others (AC3)", () => {
    render(<ReviewForm {...props()} />);
    expect(screen.getByLabelText("Diagnose 1")).toHaveValue("Herzinsuffizienz");
    expect(screen.queryByDisplayValue("Asthma")).toBeNull();
    expect(screen.queryByDisplayValue("Erfundol")).toBeNull();
    expect(screen.getAllByText(/nicht im Dokument gefunden/)).toHaveLength(2);
    expect(screen.getByText(/Erfundol 50 mg/)).toBeInTheDocument(); // shown as a note only
  });

  it("says when there is no suggestion at all (AC2)", () => {
    render(<ReviewForm {...props({ suggestion: null, candidate: null, changes: [], diffHash: null })} />);
    expect(screen.getByText("Kein Vorschlag möglich – bitte manuell erfassen")).toBeInTheDocument();
  });

  it("enables approval only after the resident is confirmed (AC5)", () => {
    render(<ReviewForm {...props()} />);
    expect(screen.getByLabelText("Bewohner")).toHaveValue("r1");
    const approve = screen.getByRole("button", { name: "Freigeben" });
    expect(approve).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Bewohner bestätigen"));
    expect(approve).toBeEnabled();
  });

  it("preselects nobody when no resident fits (AC6)", () => {
    render(<ReviewForm {...props({ candidate: null, changes: [], diffHash: null })} />);
    expect(screen.getByLabelText("Bewohner")).toHaveValue("");
    expect(screen.getByText("Bewohner bitte auswählen")).toBeInTheDocument();
  });

  it("resets the confirmation and recomputes the comparison for another resident (AC6a)", async () => {
    const fetch = vi.fn().mockResolvedValue(
      json({
        medication_changes: [{ kind: "changed", name: "Torasemid", medication_id: "m", before: null, after: null }],
        diff_hash: "h2",
      }),
    );
    vi.stubGlobal("fetch", fetch);
    render(<ReviewForm {...props()} />);
    fireEvent.click(screen.getByLabelText("Bewohner bestätigen"));
    fireEvent.change(screen.getByLabelText("Bewohner"), { target: { value: "r2" } });

    expect(screen.getByLabelText("Bewohner bestätigen")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Freigeben" })).toBeDisabled();
    await act(() => vi.advanceTimersByTimeAsync(600));
    const [url, init] = fetch.mock.calls.at(-1)!;
    expect(url).toBe("/api/documents/d1/medication-diff");
    expect(JSON.parse(init.body)).toMatchObject({ resident_id: "r2", doc_type: "medikationsplan" });
    expect(await screen.findByText("geändert")).toBeInTheDocument();
  });

  it("shows the comparison with badges (AC7)", () => {
    render(
      <ReviewForm
        {...props({
          changes: ["new", "changed", "unchanged", "discontinued"].map((kind, i) => ({
            kind,
            name: `Mittel ${i}`,
            medication_id: null,
            before: null,
            after: null,
          })),
        })}
      />,
    );
    const list = screen.getByRole("list", { name: "Medikationsabgleich" });
    for (const label of ["neu", "geändert", "unverändert", "abgesetzt"]) {
      expect(within(list).getByText(label)).toBeInTheDocument();
    }
  });

  it("adds and removes list entries (AC4)", () => {
    render(<ReviewForm {...props()} />);
    fireEvent.click(screen.getByRole("button", { name: "Diagnose hinzufügen" }));
    expect(screen.getByLabelText("Diagnose 2")).toHaveValue("");
    fireEvent.click(screen.getByRole("button", { name: "Diagnose 1 entfernen" }));
    expect(screen.queryByDisplayValue("Herzinsuffizienz")).toBeNull();
  });

  it("sends the checked values and shows a changed record with the new comparison (AC8a)", async () => {
    const fetch = vi.fn().mockResolvedValue(
      json(
        {
          error_code: "record_changed",
          message: "Die Akte wurde inzwischen geändert – bitte Abgleich prüfen",
          medication_changes: [{ kind: "unchanged", name: "Torasemid", medication_id: "m", before: null, after: null }],
          diff_hash: "h9",
        },
        409,
      ),
    );
    vi.stubGlobal("fetch", fetch);
    render(<ReviewForm {...props()} />);
    fireEvent.click(screen.getByLabelText("Bewohner bestätigen"));
    fireEvent.click(screen.getByRole("button", { name: "Freigeben" }));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/documents/d1/approve");
    expect(JSON.parse(init.body)).toEqual({
      resident_id: "r1",
      resident_confirmed: true,
      diff_hash: "h1",
      doc_type: "medikationsplan",
      document_date: "2026-10-22",
      diagnoses: ["Herzinsuffizienz"],
      medications: [{ name: "Torasemid", strength: "10 mg", dosage: DOSE, hint: null }],
      follow_ups: [],
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Die Akte wurde inzwischen geändert");
    expect(screen.getByText("unverändert")).toBeInTheDocument();
  });

  it("switches between original and fields on small screens (AC4)", () => {
    render(<ReviewForm {...props()} />);
    const original = screen.getByRole("button", { name: "Original" });
    fireEvent.click(original);
    expect(original).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Felder" })).toHaveAttribute("aria-pressed", "false");
  });
});
