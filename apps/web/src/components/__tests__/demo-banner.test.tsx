import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DemoBanner } from "@/components/demo-banner";
import { SiteFooter } from "@/components/site-footer";

describe("DemoBanner", () => {
  it("shows the exact sample-data notice", () => {
    render(<DemoBanner />);
    expect(screen.getByRole("status")).toHaveTextContent(
      /^MUSTERDATEN · keine echten Personen$/,
    );
  });
});

describe("SiteFooter", () => {
  it("shows the exact independence disclaimer", () => {
    render(<SiteFooter />);
    expect(screen.getByTestId("disclaimer")).toHaveTextContent(
      /^Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt$/,
    );
  });

  // F10-AC15
  it("says that the data is reset every night", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("contentinfo")).toHaveTextContent(
      "Alle Daten werden jede Nacht um 3 Uhr auf die Musterdaten zurückgesetzt.",
    );
  });
});
