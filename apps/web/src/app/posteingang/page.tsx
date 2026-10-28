import { Suspense } from "react";

import { ApiStatusBoundary } from "@/components/api-status";
import { Inbox } from "@/components/inbox";
import type { InboxDocument } from "@/components/inbox-list";
import { getAsCaller } from "@/lib/as-caller";
import { requireSession } from "@/lib/auth/current";

// Screen 2: inbox of the own wards (F02). The list comes from the API under RLS.
export default function InboxPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Posteingang</h1>
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <InboxSection />
      </Suspense>
    </main>
  );
}

async function InboxSection() {
  const { session } = await requireSession();
  const result = await getAsCaller<InboxDocument[]>("/documents");
  if (result.status === 503) return <ApiStatusBoundary />;
  const documents = result.data ?? [];
  // F02-AC12: only the PDL chooses the ward; nurses always upload into their own.
  const wards = session.appRole === "pdl" ? ["wb1", "wb2"] : undefined;
  return <Inbox initial={documents} wards={wards} />;
}
