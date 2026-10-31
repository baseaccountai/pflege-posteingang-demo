import Link from "next/link";
import { Suspense } from "react";

import { AgentChat } from "@/components/agent-chat";
import { ApiStatusBoundary } from "@/components/api-status";
import { QuestionChat } from "@/components/question-chat";
import { listResidents } from "@/lib/residents";

type Mode = "fragen" | "agent";

// Screen 4: questions about the documents of the own wards, answered with sources (F05) -
// or, switched to "Agent", tasks for the agent with confirmed actions (F08).
export default async function QuestionsPage({ searchParams }: PageProps<"/fragen">) {
  const { modus } = await searchParams;
  const mode: Mode = modus === "agent" ? "agent" : "fragen";
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">{mode === "agent" ? "Agent mit bestätigten Aktionen" : "Fragen an die Dokumente"}</h1>
      <nav aria-label="Ansicht" className="flex gap-2">
        <ModeLink mode="fragen" active={mode} label="Fragen" />
        <ModeLink mode="agent" active={mode} label="Agent" />
      </nav>
      <p className="text-muted-foreground text-sm">
        {mode === "agent"
          ? "Der Agent nutzt Werkzeuge mit deinen Rechten und schlägt Wiedervorlagen vor – gespeichert wird erst nach deiner Bestätigung."
          : "Die Antwort stützt sich nur auf freigegebene Dokumente deines Wohnbereichs und nennt ihre Quellen."}
      </p>
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <Chat mode={mode} searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

function ModeLink({ mode, active, label }: { mode: Mode; active: Mode; label: string }) {
  const current = mode === active;
  return (
    <Link
      href={mode === "agent" ? "/fragen?modus=agent" : "/fragen"}
      aria-current={current ? "page" : undefined}
      className={`rounded-md border px-3 py-1 text-sm ${current ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
    >
      {label}
    </Link>
  );
}

async function Chat({ mode, searchParams }: { mode: Mode } & Pick<PageProps<"/fragen">, "searchParams">) {
  const result = await listResidents();
  if (result.status === 503) return <ApiStatusBoundary />;
  const residents = (result.data ?? []).map(({ id, display_name }) => ({ id, display_name }));
  // F05-AC5: the link from a record preselects its resident - only one of the own wards.
  const { bewohner } = await searchParams;
  const chosen = typeof bewohner === "string" && residents.some((r) => r.id === bewohner) ? bewohner : "";
  return mode === "agent" ? (
    <AgentChat residents={residents} initialResident={chosen} />
  ) : (
    <QuestionChat residents={residents} initialResident={chosen} />
  );
}
