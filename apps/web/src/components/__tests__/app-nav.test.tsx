// F11-AC4: the four areas in fixed order, the current one marked.
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppNav } from "@/components/app-nav";

const pathname = vi.hoisted(() => ({ current: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

describe("AppNav", () => {
  it("shows Start, Posteingang, Bewohner and Fragen in this order", () => {
    render(<AppNav />);
    const links = screen.getAllByRole("link");
    expect(links.map((l) => [l.textContent, l.getAttribute("href")])).toEqual([
      ["Start", "/"],
      ["Posteingang", "/posteingang"],
      ["Bewohner", "/bewohner"],
      ["Fragen", "/fragen"],
    ]);
    expect(screen.getByRole("navigation", { name: "Hauptnavigation" })).toBeInTheDocument();
  });

  it.each([
    ["/", "Start"],
    ["/posteingang/abc", "Posteingang"],
    ["/bewohner/r1", "Bewohner"],
    ["/fragen", "Fragen"],
  ])("marks the area of %s as current", (path, name) => {
    pathname.current = path;
    render(<AppNav />);
    expect(screen.getByRole("link", { name })).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link").filter((l) => l.hasAttribute("aria-current"))).toHaveLength(1);
  });
});
