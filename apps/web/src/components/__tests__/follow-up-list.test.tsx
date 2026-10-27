// F04-AC5, AC8: follow-ups with origin, due ones red, "erledigt" through the BFF.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FollowUpList } from "@/components/follow-up-list";
import type { RecordFollowUp } from "@/lib/residents";

vi.mock("@/lib/navigation", () => ({ goTo: vi.fn(), leaveEndedSession: vi.fn() }));
import { goTo, leaveEndedSession } from "@/lib/navigation";

const entry = (over: Partial<RecordFollowUp>): RecordFollowUp => ({
  id: "f1",
  title: "Kontrolle Blutzucker",
  due_date: "2026-10-30",
  status: "open",
  overdue: false,
  done_by_name: null,
  done_at: null,
  provenance: {
    document_id: "d1",
    doc_type: "arztbrief",
    document_date: "2026-10-12",
    actor_type: "human",
    confirmed_by_name: "Pflegekraft WB1",
    confirmed_at: "2026-10-24T08:00:00Z",
  },
  ...over,
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("FollowUpList", () => {
  it("shows title, due date and origin", () => {
    render(<FollowUpList residentId="r1" followUps={[entry({})]} />);
    const row = screen.getByTestId("follow-up-f1");
    expect(row).toHaveTextContent("Kontrolle Blutzucker");
    expect(row).toHaveTextContent("fällig 30.10.2026");
    expect(row).toHaveTextContent("Arztbrief vom 12.10.2026");
  });

  it("highlights due follow-ups in red", () => {
    render(<FollowUpList residentId="r1" followUps={[entry({ overdue: true })]} />);
    expect(within(screen.getByTestId("follow-up-f1")).getByText("fällig 30.10.2026").className).toMatch(
      /destructive|red/,
    );
  });

  it("marks a follow-up done and reloads the record", async () => {
    const fetch = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    render(<FollowUpList residentId="r1" followUps={[entry({})]} />);
    fireEvent.click(screen.getByRole("button", { name: "Kontrolle Blutzucker als erledigt markieren" }));
    await waitFor(() => expect(goTo).toHaveBeenCalledWith("/bewohner/r1"));
    expect(fetch).toHaveBeenCalledWith("/api/follow-ups/f1/done", { method: "POST" });
  });

  it("shows the server's message when it fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Wiedervorlage ist bereits erledigt." }), { status: 409 })));
    render(<FollowUpList residentId="r1" followUps={[entry({})]} />);
    fireEvent.click(screen.getByRole("button", { name: /als erledigt markieren/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wiedervorlage ist bereits erledigt.");
    expect(goTo).not.toHaveBeenCalled();
  });

  it("leaves an ended session", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 401 })));
    render(<FollowUpList residentId="r1" followUps={[entry({})]} />);
    fireEvent.click(screen.getByRole("button", { name: /als erledigt markieren/ }));
    await waitFor(() => expect(leaveEndedSession).toHaveBeenCalled());
  });

  it("shows done ones with who and when, without a button", () => {
    render(
      <FollowUpList
        residentId="r1"
        followUps={[entry({ status: "done", done_by_name: "Pflegekraft WB1", done_at: "2026-10-26T09:00:00Z" })]}
      />,
    );
    const row = screen.getByTestId("follow-up-f1");
    expect(row).toHaveTextContent("erledigt von Pflegekraft WB1 am 26.10.2026");
    expect(within(row).queryByRole("button")).toBeNull();
  });

  it("says so when there are none", () => {
    render(<FollowUpList residentId="r1" followUps={[]} />);
    expect(screen.getByText("Keine Wiedervorlagen.")).toBeInTheDocument();
  });
});
