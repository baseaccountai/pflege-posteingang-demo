import { Suspense } from "react";

import { ResidentList } from "@/components/resident-list";
import { listResidents } from "@/lib/residents";

// Screen 6 (F04-AC1, AC2): residents of the own wards with "Neu" and follow-ups.
export default function ResidentsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Bewohner</h1>
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <Residents />
      </Suspense>
    </main>
  );
}

async function Residents() {
  return <ResidentList residents={await listResidents()} />;
}
