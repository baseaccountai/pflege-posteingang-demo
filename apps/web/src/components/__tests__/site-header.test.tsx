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

  it("leaves the areas to the main navigation (F11-AC4)", () => {
    render(<SiteHeader roleLabel="Pflegekraft WB1" />);
    expect(screen.queryByRole("link", { name: "Posteingang" })).toBeNull();
  });

  // F09-AC2: the project description is one click away on every page, signed in or not.
  it.each([["Pflegekraft WB1"], [null]])("links 'Über das Projekt' (role %s)", (role) => {
    render(<SiteHeader roleLabel={role} />);
    expect(screen.getByRole("link", { name: "Über das Projekt" })).toHaveAttribute("href", "/projekt");
  });

  it("shows no logout button without a session", () => {
    render(<SiteHeader roleLabel={null} />);
    expect(screen.getByRole("banner")).toHaveTextContent("Nicht angemeldet");
    expect(screen.queryByRole("button", { name: "Abmelden" })).toBeNull();
  });
});
