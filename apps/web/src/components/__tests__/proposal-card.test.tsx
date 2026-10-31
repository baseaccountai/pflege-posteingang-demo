// F08-AC5, AC6: a proposal of the agent is only a proposal - the nurse confirms or dismisses
// it; a failed save can be repeated.
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProposalCard } from "@/components/proposal-card";

vi.mock("@/lib/navigation", () => ({ goTo: vi.fn(), leaveEndedSession: vi.fn() }));
import { leaveEndedSession } from "@/lib/navigation";

const PROPOSAL = {
  id: "p1",
  resident: "Hr. Muster-Bauer",
  title: "Dosis mit Hausarzt klären",
  due_date: "2026-11-03",
  expires_at: "2026-10-31T23:15:00+00:00",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("ProposalCard", () => {
  it("shows what would be saved and that nothing is saved yet", () => {
    render(<ProposalCard proposal={PROPOSAL} />);
    const card = screen.getByTestId("proposal-p1");
    expect(card).toHaveTextContent("Vorschlag des Agenten");
    expect(card).toHaveTextContent("Hr. Muster-Bauer");
    expect(card).toHaveTextContent("Dosis mit Hausarzt klären");
    expect(card).toHaveTextContent("fällig am 03.11.2026");
    expect(card).toHaveTextContent("Noch nicht gespeichert");
    expect(card).toHaveTextContent("gültig bis 00:15 Uhr");
  });

  it("confirms through the BFF and then says it is in the record", async () => {
    const fetch = vi.fn().mockResolvedValue(json({ follow_up_id: "f1" }));
    vi.stubGlobal("fetch", fetch);
    render(<ProposalCard proposal={PROPOSAL} />);
    fireEvent.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(await screen.findByText("Bestätigt – Wiedervorlage in der Akte angelegt.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/agent/proposals/p1/confirm", { method: "POST" });
    expect(screen.queryByRole("button", { name: "Bestätigen" })).not.toBeInTheDocument();
  });

  it("dismisses through the BFF and saves nothing", async () => {
    const fetch = vi.fn().mockResolvedValue(json({ ok: true }));
    vi.stubGlobal("fetch", fetch);
    render(<ProposalCard proposal={PROPOSAL} />);
    fireEvent.click(screen.getByRole("button", { name: "Verwerfen" }));
    expect(await screen.findByText("Verworfen – nichts gespeichert.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/agent/proposals/p1/dismiss", { method: "POST" });
  });

  it("shows why a proposal can no longer be decided", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ error_code: "proposal_expired", message: "Der Vorschlag ist abgelaufen." }, 409)));
    render(<ProposalCard proposal={PROPOSAL} />);
    fireEvent.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Der Vorschlag ist abgelaufen.");
    expect(screen.queryByRole("button", { name: "Bestätigen" })).not.toBeInTheDocument();
  });

  it("offers to try again when saving failed", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json({ error_code: "agent_unavailable", message: "Der Agent ist gerade nicht verfügbar." }, 503))
      .mockResolvedValueOnce(json({ follow_up_id: "f1" }));
    vi.stubGlobal("fetch", fetch);
    render(<ProposalCard proposal={PROPOSAL} />);
    fireEvent.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Speichern fehlgeschlagen – erneut versuchen");
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByText("Bestätigt – Wiedervorlage in der Akte angelegt.")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("tries again what failed - a failed dismissal is never turned into a confirmation", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json({}, 500)).mockResolvedValueOnce(json({ ok: true }));
    vi.stubGlobal("fetch", fetch);
    render(<ProposalCard proposal={PROPOSAL} />);
    fireEvent.click(screen.getByRole("button", { name: "Verwerfen" }));
    fireEvent.click(await screen.findByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByText("Verworfen – nichts gespeichert.")).toBeInTheDocument();
    expect(fetch).toHaveBeenLastCalledWith("/api/agent/proposals/p1/dismiss", { method: "POST" });
  });

  it("leaves an ended session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({}, 401)));
    render(<ProposalCard proposal={PROPOSAL} />);
    fireEvent.click(screen.getByRole("button", { name: "Bestätigen" }));
    await vi.waitFor(() => expect(leaveEndedSession).toHaveBeenCalled());
  });
});
