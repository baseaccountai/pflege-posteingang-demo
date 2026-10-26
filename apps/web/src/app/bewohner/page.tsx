import Link from "next/link";
import { Suspense } from "react";

import { listResidents } from "@/lib/residents";

// Screen 6 (minimal for F01; F04 adds notes and follow-ups).
export default function ResidentsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Bewohner</h1>
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <ResidentList />
      </Suspense>
    </main>
  );
}

async function ResidentList() {
  const residents = await listResidents();
  if (residents.length === 0) return <p className="text-muted-foreground">Keine Bewohner.</p>;
  return (
    <ul className="divide-y rounded-lg border">
      {residents.map((resident) => (
        <li key={resident.id} className="flex justify-between px-3 py-2">
          <Link href={`/bewohner/${resident.id}`} className="underline">
            {resident.display_name}
          </Link>
          <span className="text-muted-foreground">{resident.ward_id.toUpperCase()}</span>
        </li>
      ))}
    </ul>
  );
}
