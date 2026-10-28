// F04 record view, shared by /bewohner/[id] (live, through the BFF) and /muster (F10-AC14:
// static, no login, no API).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResidentRecordView } from "@/components/resident-record";
import data from "@/content/sample-record.json";
import type { ResidentRecord } from "@/lib/residents";
import { sampleRecord } from "@/lib/sample-record";

vi.mock("@/lib/navigation", () => ({ goTo: vi.fn(), leaveEndedSession: vi.fn() }));
import { goTo } from "@/lib/navigation";

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

// F05-AC1a: whether a document can already be asked about, and a retry if indexing failed.
describe("ResidentRecordView documents and search", () => {
  type Indexing = ResidentRecord["documents"][number]["indexing_status"];
  const withStatus = (indexing_status: Indexing): ResidentRecord => ({
    ...record,
    documents: [{ ...record.documents[0], indexing_status }],
  });

  it("says a failed document is not searchable yet and starts it again", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 202 }));
    vi.stubGlobal("fetch", fetch);
    render(<ResidentRecordView record={withStatus("failed")} />);
    const documents = screen.getByRole("region", { name: "Dokumente" });
    expect(within(documents).getByText(/noch nicht durchsuchbar/)).toBeInTheDocument();
    fireEvent.click(within(documents).getByRole("button", { name: /Erneut versuchen/ }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(`/api/documents/${record.documents[0].id}/reindex`, { method: "POST" }),
    );
    await waitFor(() => expect(goTo).toHaveBeenCalledWith(`/bewohner/${record.resident.id}`));
    vi.unstubAllGlobals();
  });

  it("says when a document is still being prepared", () => {
    render(<ResidentRecordView record={withStatus("pending")} />);
    expect(screen.getByText(/wird für Fragen vorbereitet/)).toBeInTheDocument();
  });

  it("shows nothing extra once it is searchable, and no retry in the sample record", () => {
    render(<ResidentRecordView record={withStatus("done")} />);
    expect(screen.queryByText(/durchsuchbar|vorbereitet/)).not.toBeInTheDocument();
    render(<ResidentRecordView record={withStatus("failed")} sample />);
    expect(screen.queryByRole("button", { name: /Erneut versuchen/ })).not.toBeInTheDocument();
  });
});
