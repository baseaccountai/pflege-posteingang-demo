// F04 record view, shared by /bewohner/[id] (live, through the BFF) and /muster (F10-AC14:
// static, no login, no API).
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResidentRecordView } from "@/components/resident-record";
import data from "@/content/sample-record.json";
import { sampleRecord } from "@/lib/sample-record";

vi.mock("@/lib/navigation", () => ({ goTo: vi.fn(), leaveEndedSession: vi.fn() }));

const record = sampleRecord(data.generated_on);

function documentLinks(): string[] {
  return screen
    .getAllByRole("link")
    .map((link) => link.getAttribute("href") ?? "")
    .filter((href) => href.includes("5eed"));
}

describe("ResidentRecordView as sample record", () => {
  it("shows the resident with medication, origin and documents", () => {
    render(<ResidentRecordView record={record} sample />);
    expect(screen.getByRole("heading", { level: 1, name: "Fr. Beispiel" })).toBeInTheDocument();
    const medication = screen.getByRole("region", { name: "Medikation" });
    expect(within(medication).getByText("Metamizol 500 mg")).toBeInTheDocument();
    expect(within(medication).getAllByTestId("provenance").length).toBeGreaterThan(0);
    expect(within(medication).getByText("Ibuprofen 400 mg")).toBeInTheDocument();
    const documents = screen.getByRole("region", { name: "Dokumente" });
    expect(within(documents).getAllByRole("link")).toHaveLength(2);
  });

  it("opens the originals as static files, never through the API", () => {
    render(<ResidentRecordView record={record} sample />);
    const hrefs = documentLinks();
    expect(hrefs.length).toBeGreaterThan(0);
    for (const href of hrefs) expect(href).toMatch(/^\/muster\/5eed[0-9a-f-]+\.pdf$/);
  });

  it("offers nothing that needs a login", () => {
    render(<ResidentRecordView record={record} sample />);
    expect(screen.queryByRole("button", { name: /erledigt/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Fragen zu diesem Bewohner" })).not.toBeInTheDocument();
    // The agent's follow-up (F04-AC6) is still visible, only without the button.
    const followUps = screen.getByRole("region", { name: "Wiedervorlagen" });
    expect(within(followUps).getByText(/vom Agenten angelegt/)).toBeInTheDocument();
  });
});

describe("ResidentRecordView live", () => {
  it("links originals through the BFF and offers questions and done", () => {
    render(<ResidentRecordView record={record} />);
    for (const href of documentLinks()) expect(href).toMatch(/^\/api\/documents\/5eed[0-9a-f-]+\/file$/);
    expect(screen.getByRole("link", { name: "Fragen zu diesem Bewohner" })).toHaveAttribute(
      "href",
      `/fragen?bewohner=${record.resident.id}`,
    );
    expect(screen.getAllByRole("button", { name: /als erledigt markieren/ }).length).toBeGreaterThan(0);
  });
});
