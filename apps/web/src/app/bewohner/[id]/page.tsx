import { Suspense } from "react";

import { NoAccess } from "@/components/no-access";
import { getResident } from "@/lib/residents";

// Screen 7 (minimal for F01; F04 adds medication, diagnoses and sources) or screen 8.
export default function ResidentPage({ params }: PageProps<"/bewohner/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <ResidentDetails params={params} />
      </Suspense>
    </main>
  );
}

async function ResidentDetails({ params }: Pick<PageProps<"/bewohner/[id]">, "params">) {
  const { id } = await params;
  const resident = await getResident(id);
  if (!resident) return <NoAccess />;
  return (
    <section className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">{resident.display_name}</h1>
      <p className="text-muted-foreground">
        Wohnbereich {resident.ward_id.toUpperCase()}
        {resident.room ? ` · Zimmer ${resident.room}` : ""}
      </p>
    </section>
  );
}
