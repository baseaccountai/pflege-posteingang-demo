// F04-AC4, AC5: active medications with dosage and marks, stopped ones struck through,
// origin of the latest change, full history unfoldable.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MedicationList } from "@/components/medication-list";
import type { ProvenanceData } from "@/components/provenance";
import type { RecordMedication } from "@/lib/residents";

const DOSE = { morgens: "1", mittags: "0", abends: "1", nachts: "0" };

const prov = (over: Partial<ProvenanceData> = {}): ProvenanceData => ({
  document_id: "d2",
  doc_type: "medikationsplan",
  document_date: "2026-10-22",
  actor_type: "human",
  confirmed_by_name: "Pflegekraft WB1",
  confirmed_at: "2026-10-24T08:00:00Z",
  ...over,
});

const med = (over: Partial<RecordMedication>): RecordMedication => ({
  id: "m1",
  name: "Ramipril",
  strength: "5 mg",
  dosage: DOSE,
  status: "active",
  marker: null,
  previous: null,
  provenance: prov(),
  events: [],
  ...over,
});

describe("MedicationList", () => {
  it("shows name, strength and dosage morning-noon-evening-night", () => {
    render(<MedicationList active={[med({})]} discontinued={[]} />);
    const row = screen.getByTestId("medication-m1");
    expect(row).toHaveTextContent("Ramipril 5 mg");
    expect(row).toHaveTextContent("1-0-1-0");
    expect(row).toHaveTextContent("Medikationsplan vom 22.10.2026");
  });

  it("marks new and changed medications, with the value before", () => {
    render(
      <MedicationList
        active={[
          med({ id: "a", marker: "new" }),
          med({
            id: "b",
            name: "Metformin",
            strength: "1000 mg",
            marker: "changed",
            previous: { name: "Metformin", strength: "500 mg", dosage: { morgens: "1", mittags: "0", abends: "0", nachts: "0" } },
          }),
        ]}
        discontinued={[]}
      />,
    );
    expect(within(screen.getByTestId("medication-a")).getByText("neu")).toBeInTheDocument();
    expect(screen.getByTestId("medication-b")).toHaveTextContent("geändert (vorher: 500 mg, 1-0-0-0)");
  });

  it("strikes through stopped medications with date and document", () => {
    render(
      <MedicationList
        active={[]}
        discontinued={[
          med({
            id: "s",
            name: "Simvastatin",
            status: "discontinued",
            discontinued_at: "2026-10-24T08:00:00Z",
            provenance: prov({ doc_type: "medikationsplan", document_date: "2026-10-22" }),
          }),
        ]}
      />,
    );
    const row = screen.getByTestId("medication-s");
    expect(row).toHaveTextContent("abgesetzt am 24.10.2026 laut Medikationsplan vom 22.10.2026");
    expect(within(row).getByText(/Simvastatin/).closest("s, del, .line-through")).not.toBeNull();
  });

  it("unfolds the full history new -> changed -> stopped", () => {
    render(
      <MedicationList
        active={[]}
        discontinued={[
          med({
            id: "s",
            status: "discontinued",
            discontinued_at: "2026-10-24T08:00:00Z",
            events: [
              { kind: "new", before: null, after: { name: "Ramipril", strength: "5 mg", dosage: DOSE }, created_at: "2026-09-01T08:00:00Z", provenance: prov({ document_date: "2026-08-30" }) },
              { kind: "changed", before: { name: "Ramipril", strength: "5 mg", dosage: DOSE }, after: { name: "Ramipril", strength: "10 mg", dosage: DOSE }, created_at: "2026-10-01T08:00:00Z", provenance: prov({ doc_type: "arztbrief", document_date: "2026-09-30" }) },
              { kind: "discontinued", before: { name: "Ramipril", strength: "10 mg", dosage: DOSE }, after: null, created_at: "2026-10-24T08:00:00Z", provenance: prov() },
            ],
          }),
        ]}
      />,
    );
    const row = screen.getByTestId("medication-s");
    fireEvent.click(within(row).getByText("Verlauf (3)"));
    const items = within(row).getAllByRole("listitem").map((li) => li.textContent);
    expect(items[0]).toContain("angesetzt: 5 mg, 1-0-1-0");
    expect(items[1]).toContain("geändert: 5 mg, 1-0-1-0 → 10 mg, 1-0-1-0");
    expect(items[1]).toContain("Arztbrief vom 30.09.2026");
    expect(items[2]).toContain("abgesetzt");
  });

  it("says so when there is no medication", () => {
    render(<MedicationList active={[]} discontinued={[]} />);
    expect(screen.getByText("Keine Medikation erfasst.")).toBeInTheDocument();
  });
});
