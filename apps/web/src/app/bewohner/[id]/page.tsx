import { Suspense } from "react";

import { ApiStatusBoundary } from "@/components/api-status";
import { NoAccess } from "@/components/no-access";
import { ResidentRecordView } from "@/components/resident-record";
import { getRecord } from "@/lib/residents";

// Screen 7 (F04): the record, every entry with its origin - or screen 8 (F04-AC9).
export default function ResidentPage({ params }: PageProps<"/bewohner/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <ResidentRecord params={params} />
      </Suspense>
    </main>
  );
}

async function ResidentRecord({ params }: Pick<PageProps<"/bewohner/[id]">, "params">) {
  const { id } = await params;
  const result = await getRecord(id);
  if (result.status === 503) return <ApiStatusBoundary />;
  if (!result.data) return <NoAccess />;
  return <ResidentRecordView record={result.data} />;
}
