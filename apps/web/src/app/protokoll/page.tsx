import { Suspense } from "react";

import { ApiStatusBoundary } from "@/components/api-status";
import { AuditList } from "@/components/audit-list";
import { getAsCaller } from "@/lib/as-caller";
import type { AuditPage } from "@/lib/audit";
import { requireSession } from "@/lib/auth/current";

// Screen "Protokoll" (F12): who did what with AI - human or agent, with which model, and
// what was blocked. Only the PDL (F12-AC6); the API and RLS refuse it to everyone else too.
export default function AuditLogPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <AuditLog />
      </Suspense>
    </main>
  );
}

async function AuditLog() {
  const { session } = await requireSession();
  if (session.appRole !== "pdl") return <NoAuditAccess />;
  const result = await getAsCaller<AuditPage>("/audit");
  if (result.status === 503) return <ApiStatusBoundary />;
  return (
    <>
      <h1 className="text-2xl font-semibold">Protokoll</h1>
      <p className="text-muted-foreground text-sm">
        Jeder KI-Schritt und jede Blockierung, neueste zuerst. Das Protokoll enthält keine
        Dokument- oder Fragetexte und lässt sich nachträglich nicht ändern.
      </p>
      <AuditList initial={result.data ?? { events: [], next_before: null }} />
    </>
  );
}

function NoAuditAccess() {
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-semibold">Kein Zugriff</h1>
      <p className="text-muted-foreground">
        Das Protokoll sieht nur die Pflegedienstleitung. Die Datenbank gibt es anderen Rollen
        gar nicht erst heraus (Row Level Security).
      </p>
    </section>
  );
}
