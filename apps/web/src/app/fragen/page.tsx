import { Suspense } from "react";

import { ApiStatusBoundary } from "@/components/api-status";
import { QuestionChat } from "@/components/question-chat";
import { listResidents } from "@/lib/residents";

// Screen 4 (F05): questions about the documents of the own wards, answered with sources.
export default function QuestionsPage({ searchParams }: PageProps<"/fragen">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Fragen an die Dokumente</h1>
      <p className="text-muted-foreground text-sm">
        Die Antwort stützt sich nur auf freigegebene Dokumente deines Wohnbereichs und nennt
        ihre Quellen.
      </p>
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <Questions searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function Questions({ searchParams }: Pick<PageProps<"/fragen">, "searchParams">) {
  const result = await listResidents();
  if (result.status === 503) return <ApiStatusBoundary />;
  const residents = (result.data ?? []).map(({ id, display_name }) => ({ id, display_name }));
  // F05-AC5: the link from a record preselects its resident - only one of the own wards.
  const { bewohner } = await searchParams;
  const chosen = typeof bewohner === "string" && residents.some((r) => r.id === bewohner) ? bewohner : "";
  return <QuestionChat residents={residents} initialResident={chosen} />;
}
