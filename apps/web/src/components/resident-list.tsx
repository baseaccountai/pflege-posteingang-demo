// Screen 6 (F04-AC1, AC2): residents of the own wards; the PDL sees them grouped by ward.
import Link from "next/link";

import type { ResidentSummary } from "@/lib/residents";

export function ResidentList({ residents }: { residents: ResidentSummary[] }) {
  if (residents.length === 0) return <p className="text-muted-foreground">Keine Bewohner.</p>;
  // The API sorts by ward, so consecutive entries form the groups.
  const wards = new Map<string, ResidentSummary[]>();
  for (const resident of residents) {
    wards.set(resident.ward_name, [...(wards.get(resident.ward_name) ?? []), resident]);
  }
  if (wards.size === 1) return <Rows residents={residents} />;
  return (
    <div className="flex flex-col gap-6">
      {[...wards].map(([ward, members]) => (
        <section key={ward} aria-label={ward} className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">{ward}</h2>
          <Rows residents={members} />
        </section>
      ))}
    </div>
  );
}

function Rows({ residents }: { residents: ResidentSummary[] }) {
  return (
    <ul className="divide-y rounded-lg border">
      {residents.map((resident) => (
        <li
          key={resident.id}
          data-testid={`resident-${resident.id}`}
          className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
        >
          <div className="flex flex-col">
            <span className="flex items-center gap-2">
              <Link href={`/bewohner/${resident.id}`} className="font-medium underline">
                {resident.display_name}
              </Link>
              {resident.has_new && (
                <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-800">
                  Neu
                </span>
              )}
            </span>
            <span className="text-muted-foreground text-sm">
              {resident.room ? `Zimmer ${resident.room} · ` : ""}
              {resident.ward_name}
            </span>
          </div>
          <FollowUpCounter open={resident.open_follow_ups} due={resident.overdue_follow_ups} />
        </li>
      ))}
    </ul>
  );
}

function FollowUpCounter({ open, due }: { open: number; due: number }) {
  if (open === 0) return null;
  return (
    <span className="flex items-center gap-2 text-sm">
      <span>
        {open} {open === 1 ? "Wiedervorlage" : "Wiedervorlagen"}
      </span>
      {due > 0 && (
        <span className="bg-destructive/10 text-destructive rounded px-1.5 py-0.5 font-medium">
          {due} fällig
        </span>
      )}
    </span>
  );
}
