// F12-AC7: the log for the PDL - newest first, filters "nur Agent" / "nur blockiert",
// "Ältere laden" below the smallest number shown, agent events marked.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditList } from "@/components/audit-list";
import type { AuditEvent } from "@/lib/audit";

vi.mock("@/lib/navigation", () => ({ goTo: vi.fn(), leaveEndedSession: vi.fn() }));
import { leaveEndedSession } from "@/lib/navigation";

function event(id: number, extra: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id,
    at: "2026-10-30T13:05:09+00:00",
    ward_id: "wb1",
    action: "question",
    outcome: "ok",
    actor_type: "human",
    actor_name: "Pflegekraft WB1",
    on_behalf_of_name: null,
    model: "mistral-small-latest",
    document_id: null,
    resident_id: null,
    resident_name: null,
    details: {},
    ...extra,
  };
}

const AGENT = event(9, {
  action: "agent_tool",
  actor_type: "agent",
  actor_name: "KI-Agent",
  on_behalf_of_name: "Pflegekraft WB1",
  details: { tool: "read_record" },
  resident_id: "r1",
  resident_name: "Hr. Muster-Bauer",
});
const BLOCKED = event(8, { action: "blocked", outcome: "blocked", model: null, details: { layer: "pattern", rule_id: "ignore-de" } });

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

const rows = () => screen.getAllByRole("listitem");

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("AuditList", () => {
  it("shows each event with time, action, outcome, actor, ward, model, resident and details", () => {
    render(<AuditList initial={{ events: [AGENT, BLOCKED], next_before: null }} />);
    const [agent, blocked] = rows();
    expect(agent).toHaveTextContent("30.10.2026, 14:05:09");
    expect(agent).toHaveTextContent("Agent-Werkzeug");
    expect(agent).toHaveTextContent("KI-Agent im Auftrag von Pflegekraft WB1");
    expect(agent).toHaveTextContent("WB1");
    expect(agent).toHaveTextContent("Modell: mistral-small-latest");
    expect(agent).toHaveTextContent("Hr. Muster-Bauer");
    expect(agent).toHaveTextContent("Werkzeug: read_record");
    expect(blocked).toHaveTextContent("Blockiert");
    expect(blocked).toHaveTextContent("Regel: ignore-de");
    expect(blocked).not.toHaveTextContent("Modell:");
    expect(screen.queryByRole("button", { name: "Ältere laden" })).not.toBeInTheDocument();
  });

  it("marks agent events so they stand out from human ones", () => {
    render(<AuditList initial={{ events: [AGENT, BLOCKED], next_before: null }} />);
    const [agent, blocked] = rows();
    expect(within(agent).getByText("Agent")).toBeInTheDocument();
    expect(agent).toHaveAttribute("data-actor", "agent");
    expect(within(blocked).queryByText("Agent")).not.toBeInTheDocument();
  });

  it("loads older events below the smallest number shown and appends them", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ events: [event(3)], next_before: null }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuditList initial={{ events: [AGENT, BLOCKED], next_before: 8 }} />);
    fireEvent.click(screen.getByRole("button", { name: "Ältere laden" }));
    await waitFor(() => expect(rows()).toHaveLength(3));
    expect(fetchMock).toHaveBeenCalledWith("/api/audit?before=8", expect.anything());
    expect(screen.queryByRole("button", { name: "Ältere laden" })).not.toBeInTheDocument();
  });

  it("filters start again from the newest event", async () => {
    // A new Response per call: a body can be read only once.
    const fetchMock = vi.fn().mockImplementation(async () => json({ events: [AGENT], next_before: null }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuditList initial={{ events: [AGENT, BLOCKED], next_before: 8 }} />);
    fireEvent.click(screen.getByLabelText("nur Agent"));
    await waitFor(() => expect(rows()).toHaveLength(1));
    expect(fetchMock).toHaveBeenLastCalledWith("/api/audit?agent_only=true", expect.anything());
    fireEvent.click(screen.getByLabelText("nur blockiert"));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith("/api/audit?agent_only=true&blocked_only=true", expect.anything()),
    );
  });

  it("shows only the answer to the latest filter, even if an older one arrives later", async () => {
    let releaseFirst: (response: Response) => void = () => {};
    const first = new Promise<Response>((resolve) => (releaseFirst = resolve));
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => first) // "nur blockiert" on: slow
      .mockImplementationOnce(async () => json({ events: [AGENT], next_before: null })); // then "nur Agent"
    vi.stubGlobal("fetch", fetchMock);
    render(<AuditList initial={{ events: [AGENT, BLOCKED], next_before: null }} />);
    fireEvent.click(screen.getByLabelText("nur blockiert"));
    fireEvent.click(screen.getByLabelText("nur Agent"));
    await waitFor(() => expect(rows()).toHaveLength(1));
    releaseFirst(json({ events: [BLOCKED, event(7), event(6)], next_before: null }));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(rows()).toHaveLength(1);
    expect(rows()[0]).toHaveAttribute("data-actor", "agent");
  });

  it("says so when there is nothing to show", () => {
    render(<AuditList initial={{ events: [], next_before: null }} />);
    expect(screen.getByText("Keine Ereignisse.")).toBeInTheDocument();
  });

  it("shows the API's message when loading fails, and leaves an ended session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ message: "Demo startet gerade" }, 503)));
    render(<AuditList initial={{ events: [AGENT], next_before: 9 }} />);
    fireEvent.click(screen.getByRole("button", { name: "Ältere laden" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Demo startet gerade");

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({}, 401)));
    fireEvent.click(screen.getByRole("button", { name: "Ältere laden" }));
    await waitFor(() => expect(leaveEndedSession).toHaveBeenCalled());
  });
});
