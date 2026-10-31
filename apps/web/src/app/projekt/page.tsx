import { connection } from "next/server";

import { AgentTokenWay } from "@/components/agent-token-way";
import { DataFlowTable } from "@/components/data-flow-table";
import { SecurityReportLink } from "@/components/requirements-map";
import { repoHref, DEFAULT_REPO_URL } from "@/content/requirements-map";
import { apiAgentTokenWay } from "@/lib/api";

// F09-AC8: placeholder in Stufe 1; the full project description follows in phase 9.
const LINKS = [
  { name: "Architektur", href: repoHref("docs/architecture/architecture.md"), note: "arc42 und Entscheidungen (ADRs)" },
  { name: "Specs", href: repoHref("docs/specs/"), note: "jedes Feature mit Akzeptanzkriterien" },
  { name: "Repository", href: process.env.NEXT_PUBLIC_REPO_URL || DEFAULT_REPO_URL, note: "der gesamte Code" },
];

export default async function ProjectPage() {
  await connection(); // the way is read at request time from the API (F08-AC2)
  const agentTokenWay = await apiAgentTokenWay();
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Über das Projekt</h1>
      <p>
        Projektbeschreibung folgt. Bis dahin: Was gebaut wird und warum, steht in der Architektur
        und in den Specs.
      </p>
      <ul className="flex flex-col gap-2">
        {LINKS.map((link) => (
          <li key={link.name}>
            <a href={link.href} target="_blank" rel="noopener" className="font-medium underline">
              {link.name}
            </a>
            <span className="text-muted-foreground text-sm"> – {link.note}</span>
          </li>
        ))}
      </ul>
      <p className="text-sm">
        Gemessene Erkennungs- und Fehlalarmrate des Schutzes vor Prompt-Injection:{" "}
        <SecurityReportLink />
      </p>
      <AgentTokenWay way={agentTokenWay} />
      <DataFlowTable />
      <p className="text-muted-foreground text-sm">
        Unabhängige Bewerbungsdemo mit erfundenen Musterdaten; alle Daten werden jede Nacht
        zurückgesetzt.
      </p>
    </main>
  );
}
