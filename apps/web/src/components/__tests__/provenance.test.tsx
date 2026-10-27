// F04-AC5, AC6: one line per entry saying where it came from and who confirmed it.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Provenance, type ProvenanceData } from "@/components/provenance";

const base: ProvenanceData = {
  document_id: "d1",
  doc_type: "arztbrief",
  document_date: "2026-10-12",
  actor_type: "human",
  confirmed_by_name: "Pflegekraft WB1",
  // 23:30 UTC is already the 25th in Berlin: dates are shown in the care home's time.
  confirmed_at: "2026-10-24T22:30:00Z",
};

describe("Provenance", () => {
  it("names document type, date and who approved it when", () => {
    render(<Provenance provenance={base} />);
    const line = screen.getByTestId("provenance");
    expect(line).toHaveTextContent("Arztbrief vom 12.10.2026 · freigegeben von Pflegekraft WB1 am 25.10.2026");
  });

  it("links the document date to the original", () => {
    render(<Provenance provenance={base} />);
    const link = screen.getByRole("link", { name: "Arztbrief vom 12.10.2026" });
    expect(link).toHaveAttribute("href", "/api/documents/d1/file");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener");
  });

  it("says when the agent created the entry and who confirmed it", () => {
    render(<Provenance provenance={{ ...base, actor_type: "agent" }} />);
    const line = screen.getByTestId("provenance");
    expect(line).toHaveTextContent("vom Agenten angelegt · bestätigt von Pflegekraft WB1 am 25.10.2026");
    expect(line).not.toHaveTextContent("freigegeben von");
  });

  it("works without a source document (sample data)", () => {
    render(
      <Provenance provenance={{ ...base, document_id: null, doc_type: null, document_date: null }} />,
    );
    expect(screen.getByTestId("provenance")).toHaveTextContent(
      "ohne Herkunftsdokument · freigegeben von Pflegekraft WB1 am 25.10.2026",
    );
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows an unknown type and a missing date plainly", () => {
    render(<Provenance provenance={{ ...base, doc_type: null, document_date: null }} />);
    expect(screen.getByRole("link", { name: "Dokument" })).toBeInTheDocument();
  });

  it("shows nothing misleading when there is no provenance", () => {
    render(<Provenance provenance={null} />);
    expect(screen.getByTestId("provenance")).toHaveTextContent("Herkunft unbekannt");
  });
});
