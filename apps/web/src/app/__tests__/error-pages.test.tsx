// F10-AC4: error pages carry banner and footer too. global-error replaces the root layout
// (it renders its own <html>), so it brings both itself.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ErrorPage from "@/app/error";
import GlobalError from "@/app/global-error";

const BANNER = "MUSTERDATEN · keine echten Personen";
const DISCLAIMER = "Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt";

describe("ErrorPage", () => {
  it("explains in German, without details, and offers a retry", () => {
    const reset = vi.fn();
    render(<ErrorPage error={Object.assign(new Error("secret detail"), { digest: "abc" })} reset={reset} />);
    expect(screen.getByRole("heading", { level: 1, name: "Etwas ist schiefgelaufen" })).toBeInTheDocument();
    expect(screen.queryByText(/secret detail/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(reset).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Musterakte ansehen" })).toHaveAttribute("href", "/muster");
  });
});

describe("GlobalError", () => {
  it("brings banner and footer itself", () => {
    // Renders <html>/<body>; jsdom warns about nesting, the content is what counts here.
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<GlobalError error={new Error("x")} reset={vi.fn()} />);
    expect(screen.getByText(BANNER)).toBeInTheDocument();
    expect(screen.getByTestId("disclaimer")).toHaveTextContent(DISCLAIMER);
    expect(screen.getByRole("heading", { level: 1, name: "Etwas ist schiefgelaufen" })).toBeInTheDocument();
  });
});
