"use client";
// F08: tasks for the agent. It works with the nurse's rights (RLS), uses at most four tool
// steps and writes nothing itself - a follow-up only after "Bestätigen" (AC5, AC6).
// Like the questions, the conversation lives only in this component's state (F05-AC11).
import { useState } from "react";

import { ProposalCard, type Proposal } from "@/components/proposal-card";
import { Button } from "@/components/ui/button";
import { AGENT_CANNOT, toolsUsedLine } from "@/lib/agent";
import { modelLabel } from "@/lib/models";
import { leaveEndedSession } from "@/lib/navigation";

const MAX_LENGTH = 500;

type Reply = {
  task: string;
  answer: string;
  tools: string[];
  proposals: Proposal[];
  model: string;
  stopped: boolean;
};

export function AgentChat({
  residents,
  initialResident,
}: {
  residents: { id: string; display_name: string }[];
  initialResident: string;
}) {
  const [resident, setResident] = useState(initialResident);
  const [task, setTask] = useState("");
  const [history, setHistory] = useState<Reply[]>([]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function give(event: React.FormEvent) {
    event.preventDefault();
    const text = task.trim();
    if (!text) return;
    setBusy(true);
    setProblem(null);
    try {
      const response = await fetch("/api/agent", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(resident ? { task: text, resident_id: resident } : { task: text }),
      });
      if (response.status === 401) return leaveEndedSession();
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setProblem(data.message ?? "Der Auftrag konnte nicht ausgeführt werden.");
        return;
      }
      setHistory((before) => [
        ...before,
        {
          task: text,
          answer: data.answer,
          tools: data.tools_used ?? [],
          proposals: data.proposals ?? [],
          model: data.model,
          stopped: Boolean(data.stopped),
        },
      ]);
      setTask("");
    } catch {
      setProblem("Der Auftrag konnte nicht ausgeführt werden.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-lg border bg-muted/40 p-3 text-sm">
        <p>
          Der Agent arbeitet mit <strong>deinen Rechten</strong>: Er liest Dokumente und Akten deines Wohnbereichs und
          schlägt Wiedervorlagen vor. Gespeichert wird erst, wenn du bestätigst.
        </p>
        <p className="mt-2 font-medium" id="agent-cannot">
          Das kann der Agent nicht
        </p>
        <ul aria-labelledby="agent-cannot" className="mt-1 flex flex-wrap gap-2">
          {AGENT_CANNOT.map((item) => (
            <li key={item} className="rounded-full border px-2 py-0.5 text-xs">
              {item}
            </li>
          ))}
        </ul>
      </section>

      <ol className="flex flex-col gap-3">
        {history.map((reply, index) => (
          <li key={index} data-testid={`agent-answer-${index}`} className="flex flex-col gap-2 rounded-lg border p-3">
            <p className="font-medium">{reply.task}</p>
            {reply.stopped && <p className="text-destructive text-xs font-medium">Grenze erreicht – Auftrag abgebrochen</p>}
            <p className="whitespace-pre-line">{reply.answer}</p>
            {reply.proposals.map((proposal) => (
              <ProposalCard key={proposal.id} proposal={proposal} />
            ))}
            {toolsUsedLine(reply.tools) && <p className="text-xs">{toolsUsedLine(reply.tools)}</p>}
            <p className="text-muted-foreground text-xs">Antwort von {modelLabel(reply.model)} · KI-Antwort, bitte prüfen</p>
          </li>
        ))}
      </ol>

      {problem && (
        <p role="alert" className="text-destructive text-sm">
          {problem}
        </p>
      )}

      <form onSubmit={give} className="flex flex-col gap-2 rounded-lg border p-3">
        <label className="flex flex-col gap-1 text-sm">
          Bewohner
          <select
            aria-label="Bewohner"
            value={resident}
            onChange={(event) => setResident(event.target.value)}
            className="rounded-md border px-2 py-1"
          >
            <option value="">Alle Bewohner meines Wohnbereichs</option>
            {residents.map((r) => (
              <option key={r.id} value={r.id}>
                {r.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Auftrag
          <textarea
            aria-label="Auftrag"
            value={task}
            maxLength={MAX_LENGTH}
            rows={3}
            placeholder="z. B. Gleiche den neuen Medikationsplan von Hr. Muster-Bauer mit der Akte ab."
            onChange={(event) => setTask(event.target.value)}
            className="rounded-md border px-2 py-1"
          />
        </label>
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground text-xs">
            {task.length}/{MAX_LENGTH}
          </span>
          <Button type="submit" disabled={busy || !task.trim()}>
            Auftrag geben
          </Button>
        </div>
      </form>
    </div>
  );
}
