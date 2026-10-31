"use client";
// F08-AC5, AC6: a proposal of the agent. Nothing is in the record until the nurse confirms:
// then the API sets the proposal to confirmed as her and lets the agent write the follow-up.
// If that second step fails, confirming again only repeats it ("erneut versuchen").
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { formatDate, formatTime } from "@/lib/dates";
import { leaveEndedSession } from "@/lib/navigation";

export type Proposal = {
  id: string;
  resident: string;
  title: string;
  due_date: string | null;
  expires_at: string;
};

type State =
  | { kind: "open" }
  | { kind: "busy" }
  | { kind: "confirmed" }
  | { kind: "dismissed" }
  | { kind: "closed"; message: string } // expired or decided: nothing more to do here
  | { kind: "retry"; action: Action; message: string }; // failed: the same click again

type Action = "confirm" | "dismiss";

const FAILED: Record<Action, string> = {
  confirm: "Speichern fehlgeschlagen – erneut versuchen",
  dismiss: "Verwerfen fehlgeschlagen – erneut versuchen",
};

export function ProposalCard({ proposal }: { proposal: Proposal }) {
  const [state, setState] = useState<State>({ kind: "open" });

  async function decide(action: Action) {
    setState({ kind: "busy" });
    try {
      const response = await fetch(`/api/agent/proposals/${encodeURIComponent(proposal.id)}/${action}`, { method: "POST" });
      if (response.status === 401) return leaveEndedSession();
      const data = await response.json().catch(() => ({}));
      if (response.ok) return setState({ kind: action === "confirm" ? "confirmed" : "dismissed" });
      if (response.status === 409 || response.status === 404) {
        return setState({ kind: "closed", message: data.message ?? "Der Vorschlag gilt nicht mehr." });
      }
      setState({ kind: "retry", action, message: data.message ?? "" });
    } catch {
      setState({ kind: "retry", action, message: "" });
    }
  }

  return (
    <div data-testid={`proposal-${proposal.id}`} className="flex flex-col gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-950/30">
      <p className="font-medium">Vorschlag des Agenten: Wiedervorlage</p>
      <p>
        {proposal.resident} · {proposal.title}
        {proposal.due_date && ` · fällig am ${formatDate(proposal.due_date)}`}
      </p>
      {(state.kind === "open" || state.kind === "busy") && (
        <>
          <p className="text-muted-foreground text-xs">
            Noch nicht gespeichert – erst deine Bestätigung legt die Wiedervorlage an · gültig bis{" "}
            {formatTime(proposal.expires_at)} Uhr
          </p>
          <div className="flex gap-2">
            <Button size="sm" disabled={state.kind === "busy"} onClick={() => decide("confirm")}>
              Bestätigen
            </Button>
            <Button size="sm" variant="outline" disabled={state.kind === "busy"} onClick={() => decide("dismiss")}>
              Verwerfen
            </Button>
          </div>
        </>
      )}
      {state.kind === "confirmed" && <p className="text-green-700 dark:text-green-400">Bestätigt – Wiedervorlage in der Akte angelegt.</p>}
      {state.kind === "dismissed" && <p className="text-muted-foreground">Verworfen – nichts gespeichert.</p>}
      {state.kind === "closed" && (
        <p role="alert" className="text-destructive">
          {state.message}
        </p>
      )}
      {state.kind === "retry" && (
        <>
          <p role="alert" className="text-destructive">
            {FAILED[state.action]}
            {state.message && ` (${state.message})`}
          </p>
          <div>
            <Button size="sm" onClick={() => decide(state.action)}>
              Erneut versuchen
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
