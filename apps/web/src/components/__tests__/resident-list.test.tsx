// F04-AC1, AC2: residents with room and ward, "Neu" badge, open and due follow-ups.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResidentList } from "@/components/resident-list";
import type { ResidentSummary } from "@/lib/residents";

const resident = (over: Partial<ResidentSummary>): ResidentSummary => ({
  id: "r1",
  ward_id: "wb1",
  ward_name: "WB 1",
  display_name: "Hr. Muster-Bauer",
  room: "104",
  has_new: false,
  open_follow_ups: 0,
  overdue_follow_ups: 0,
  ...over,
});

describe("ResidentList", () => {
  it("shows name as link, room and ward", () => {
    render(<ResidentList residents={[resident({})]} />);
    expect(screen.getByRole("link", { name: "Hr. Muster-Bauer" })).toHaveAttribute("href", "/bewohner/r1");
    const row = screen.getByTestId("resident-r1");
    expect(row).toHaveTextContent("Zimmer 104");
    expect(row).toHaveTextContent("WB 1");
  });

  it("shows the Neu badge only for residents with a new document", () => {
    render(<ResidentList residents={[resident({ has_new: true }), resident({ id: "r2", display_name: "Fr. Zett" })]} />);
    expect(within(screen.getByTestId("resident-r1")).getByText("Neu")).toBeInTheDocument();
    expect(within(screen.getByTestId("resident-r2")).queryByText("Neu")).toBeNull();
  });

  it("counts open follow-ups and highlights due ones in red", () => {
    render(<ResidentList residents={[resident({ open_follow_ups: 3, overdue_follow_ups: 1 })]} />);
    const row = screen.getByTestId("resident-r1");
    expect(row).toHaveTextContent("3 Wiedervorlagen");
    const due = within(row).getByText("1 fällig");
    expect(due.className).toMatch(/destructive|red/);
  });

  it("says nothing about follow-ups when there are none", () => {
    render(<ResidentList residents={[resident({})]} />);
    expect(screen.getByTestId("resident-r1")).not.toHaveTextContent("Wiedervorlage");
  });

  it("uses the singular for one follow-up", () => {
    render(<ResidentList residents={[resident({ open_follow_ups: 1 })]} />);
    expect(screen.getByTestId("resident-r1")).toHaveTextContent("1 Wiedervorlage");
    expect(screen.getByTestId("resident-r1")).not.toHaveTextContent("fällig");
  });

  it("groups by ward when there are several wards (PDL)", () => {
    render(
      <ResidentList
        residents={[resident({}), resident({ id: "r2", ward_id: "wb2", ward_name: "WB 2", display_name: "Fr. Testfeld" })]}
      />,
    );
    const wb1 = screen.getByRole("region", { name: "WB 1" });
    const wb2 = screen.getByRole("region", { name: "WB 2" });
    expect(within(wb1).getByText("Hr. Muster-Bauer")).toBeInTheDocument();
    expect(within(wb2).getByText("Fr. Testfeld")).toBeInTheDocument();
    expect(within(wb1).queryByText("Fr. Testfeld")).toBeNull();
  });

  it("says so when there are no residents", () => {
    render(<ResidentList residents={[]} />);
    expect(screen.getByText("Keine Bewohner.")).toBeInTheDocument();
  });
});
