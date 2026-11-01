import { connection } from "next/server";

import { AgentTokenWay } from "@/components/agent-token-way";
import { DataFlowTable } from "@/components/data-flow-table";
import { ProjectDescription } from "@/components/project-description";
import { SecurityReportLink } from "@/components/requirements-map";
import { apiAgentTokenWay } from "@/lib/api";

// Phase 9 (design 8.3): the project description - the same text as
// docs/projektbeschreibung.md - and below it what the running demo reports about itself.
export default async function ProjectPage() {
  await connection(); // the way is read at request time from the API (F08-AC2)
  const agentTokenWay = await apiAgentTokenWay();
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Über das Projekt</h1>
      <ProjectDescription />
      <section aria-labelledby="live-heading" className="mt-6 flex flex-col gap-3 rounded-lg border p-4">
        <h2 id="live-heading" className="text-xl font-semibold">
          Aus der laufenden Demo
        </h2>
        <p className="text-sm">
          Gemessene Erkennungs- und Fehlalarmrate des Schutzes vor Prompt-Injection:{" "}
          <SecurityReportLink />
        </p>
        <AgentTokenWay way={agentTokenWay} />
        <DataFlowTable />
      </section>
    </main>
  );
}
