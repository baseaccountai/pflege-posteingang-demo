// F06-AC11, AC12: which provider sees which data - shown on /projekt.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DataFlowTable } from "@/components/data-flow-table";

describe("DataFlowTable", () => {
  it("names for every AI step what the provider sees, publicly and locally", () => {
    render(<DataFlowTable />);
    const table = screen.getByRole("table", { name: "Welche KI sieht welche Daten" });
    const row = (step: string) => within(table).getByRole("row", { name: new RegExp(step) });
    expect(row("Texterkennung")).toHaveTextContent("Original");
    for (const step of ["Feldvorschlag", "Suche", "Antwort"]) {
      expect(row(step)).toHaveTextContent("nur Platzhalter");
    }
    expect(row("Texterkennung")).toHaveTextContent("Docling auf dem eigenen Rechner");
  });

  it("states the limit of the name recognition openly", () => {
    render(<DataFlowTable />);
    expect(screen.getByText(/Namen ohne Anrede oder Titel, die nirgends bekannt sind/)).toBeInTheDocument();
  });
});
