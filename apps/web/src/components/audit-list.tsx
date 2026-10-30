"use client";
// Screen "Protokoll" (F12-AC7): the audit log for the PDL, newest first. "Ältere laden"
// continues below the smallest number shown; a filter starts again from the newest event.
// Agent events are marked, so human and agent can be told apart at a glance (US-2).
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { auditQuery, describeEvent, type AuditEvent, type AuditPage } from "@/lib/audit";
import { formatDateTime } from "@/lib/dates";
import { leaveEndedSession } from "@/lib/navigation";

const LOAD_FAILED = "Das Protokoll konnte nicht geladen werden.";

const OUTCOME_STYLES: Record<AuditEvent["outcome"], string> = {
  ok: "border",
  blocked: "bg-red-100 font-medium text-red-900",
  error: "bg-amber-100 text-amber-950",
};

export function AuditList({ initial }: { initial: AuditPage }) {
  const [events, setEvents] = useState(initial.events);
  const [nextBefore, setNextBefore] = useState(initial.next_before);
  const [agentOnly, setAgentOnly] = useState(false);
  const [blockedOnly, setBlockedOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function load(filters: { agentOnly: boolean; blockedOnly: boolean }, before?: number) {
    setBusy(true);
    setProblem(null);
    try {
      const response = await fetch(`/api/audit${auditQuery({ ...filters, before })}`, { cache: "no-store" });
      if (response.status === 401) return leaveEndedSession();
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setProblem(data.message ?? LOAD_FAILED);
        return;
      }
      const page = data as AuditPage;
      setEvents((shown) => (before === undefined ? page.events : [...shown, ...page.events]));
      setNextBefore(page.next_before);
    } catch {
      setProblem(LOAD_FAILED);
    } finally {
      setBusy(false);
    }
  }

  function filter(change: Partial<{ agentOnly: boolean; blockedOnly: boolean }>) {
    const filters = { agentOnly, blockedOnly, ...change };
    setAgentOnly(filters.agentOnly);
    setBlockedOnly(filters.blockedOnly);
    void load(filters);
  }

  return (
    <section className="flex flex-col gap-4">
      <fieldset className="flex flex-wrap gap-4 text-sm">
        <legend className="sr-only">Filter</legend>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={agentOnly} onChange={(e) => filter({ agentOnly: e.target.checked })} />
          nur Agent
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={blockedOnly} onChange={(e) => filter({ blockedOnly: e.target.checked })} />
          nur blockiert
        </label>
      </fieldset>

      {events.length === 0 ? (
        <p className="text-muted-foreground">Keine Ereignisse.</p>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Ereignisse">
          {events.map((event) => (
            <AuditRow key={event.id} event={event} />
          ))}
        </ul>
      )}

      {problem && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-900">
          {problem}
        </p>
      )}
      {nextBefore !== null && (
        <Button variant="outline" disabled={busy} onClick={() => void load({ agentOnly, blockedOnly }, nextBefore)}>
          Ältere laden
        </Button>
      )}
    </section>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  const text = describeEvent(event);
  const agent = event.actor_type === "agent";
  return (
    <li
      data-actor={event.actor_type}
      className={`flex flex-col gap-1 rounded-lg border p-3 text-sm ${agent ? "border-l-4 border-l-violet-600 bg-violet-50/50" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground tabular-nums">{formatDateTime(event.at)}</span>
        <span className="font-medium">{text.action}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${OUTCOME_STYLES[event.outcome] ?? "border"}`}>{text.outcome}</span>
        {agent && <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-900">Agent</span>}
      </div>
      <div className="text-muted-foreground flex flex-wrap gap-x-3">
        <span>{text.actor}</span>
        <span>{event.ward_id ? event.ward_id.toUpperCase() : "ohne Wohnbereich"}</span>
        {event.model && <span>Modell: {event.model}</span>}
        {event.resident_name && <span>{event.resident_name}</span>}
        {event.document_id && (
          <Link href={`/posteingang/${event.document_id}`} className="underline">
            Dokument
          </Link>
        )}
      </div>
      {text.details.length > 0 && <div className="text-muted-foreground">{text.details.join(" · ")}</div>}
    </li>
  );
}
