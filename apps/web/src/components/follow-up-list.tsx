"use client";
// F04-AC5, AC8: follow-ups of the record; open ones can be marked done - except in the
// static sample record (F10-AC14), which has no login and no API.
import { useState } from "react";

import { Provenance } from "@/components/provenance";
import { Button } from "@/components/ui/button";
import { formatDate, formatDay } from "@/lib/dates";
import { goTo, leaveEndedSession } from "@/lib/navigation";
import type { RecordFollowUp } from "@/lib/residents";

export function FollowUpList({
  residentId,
  followUps,
  sample = false,
}: {
  residentId: string;
  followUps: RecordFollowUp[];
  sample?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  if (followUps.length === 0) return <p className="text-muted-foreground">Keine Wiedervorlagen.</p>;

  async function markDone(id: string) {
    setBusy(id);
    setProblem(null);
    const response = await fetch(`/api/follow-ups/${encodeURIComponent(id)}/done`, { method: "POST" });
    if (response.status === 401) return leaveEndedSession();
    // Full reload: counters and lists come fresh from the server (see lib/navigation.ts).
    if (response.ok) return goTo(`/bewohner/${residentId}`);
    const data = await response.json().catch(() => ({}));
    // FastAPI errors carry `detail`; reset (F10-AC7) and cold start (F10-AC13) `message`.
    setProblem(data.detail ?? data.message ?? "Erledigen nicht möglich.");
    setBusy(null);
  }

  return (
    <div className="flex flex-col gap-2">
      {problem && (
        <p role="alert" className="text-destructive text-sm">
          {problem}
        </p>
      )}
      <ul className="flex flex-col divide-y">
        {followUps.map((entry) => (
          <li key={entry.id} data-testid={`follow-up-${entry.id}`} className="flex flex-col gap-1 py-2">
            <span className="flex flex-wrap items-center justify-between gap-2">
              <span className={entry.status === "done" ? "text-muted-foreground line-through" : "font-medium"}>
                {entry.title}
              </span>
              {entry.due_date && (
                <span
                  className={
                    entry.overdue
                      ? "bg-destructive/10 text-destructive rounded px-1.5 py-0.5 text-sm font-medium"
                      : "text-muted-foreground text-sm"
                  }
                >
                  fällig {formatDate(entry.due_date)}
                </span>
              )}
            </span>
            <Provenance provenance={entry.provenance} sample={sample} />
            {entry.status === "done" ? (
              <span className="text-muted-foreground text-xs">
                erledigt von {entry.done_by_name}
                {entry.done_at ? ` am ${formatDay(entry.done_at)}` : ""}
              </span>
            ) : sample ? null : (
              <Button
                variant="outline"
                size="sm"
                className="self-start"
                disabled={busy !== null}
                aria-label={`${entry.title} als erledigt markieren`}
                onClick={() => markDone(entry.id)}
              >
                Erledigt
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
