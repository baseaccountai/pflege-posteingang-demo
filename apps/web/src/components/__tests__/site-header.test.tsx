// F01-AC20: the header shows the signed-in role and a logout button.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SiteHeader } from "@/components/site-header";

describe("SiteHeader", () => {
  it("shows the role and a logout button (form POST)", () => {
    render(<SiteHeader roleLabel="Pflegekraft WB1" />);
    const header = screen.getByRole("banner");
    expect(header).toHaveTextContent("Pflegekraft WB1");
    const form = screen.getByRole("button", { name: "Abmelden" }).closest("form")!;
    expect(form.method).toBe("post");
    expect(new URL(form.action).pathname).toBe("/auth/logout");
    expect(new URL(form.action).search).toBe("");
  });

  it("shows no logout button without a session", () => {
    render(<SiteHeader roleLabel={null} />);
    expect(screen.getByRole("banner")).toHaveTextContent("Nicht angemeldet");
    expect(screen.queryByRole("button", { name: "Abmelden" })).toBeNull();
  });
});
