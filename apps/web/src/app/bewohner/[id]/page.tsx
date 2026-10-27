import Link from "next/link";
import { Suspense, type ReactNode } from "react";

import { FollowUpList } from "@/components/follow-up-list";
import { MedicationList } from "@/components/medication-list";
import { NoAccess } from "@/components/no-access";
import { Provenance } from "@/components/provenance";
import { formatDate, formatDay } from "@/lib/dates";
import { DOC_TYPE_LABELS } from "@/lib/documents/labels";
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

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

async function ResidentRecord({ params }: Pick<PageProps<"/bewohner/[id]">, "params">) {
  const { id } = await params;
  const record = await getRecord(id);
  if (!record) return <NoAccess />;
  const { resident } = record;
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">{resident.display_name}</h1>
          <p className="text-muted-foreground">
            {resident.ward_name}
            {resident.room ? ` · Zimmer ${resident.room}` : ""}
          </p>
        </div>
        {/* F04-AC7: questions about this resident only (F05). */}
        <Link
          href={`/fragen?bewohner=${encodeURIComponent(resident.id)}`}
          className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
        >
          Fragen zu diesem Bewohner
        </Link>
      </div>

      <Card title="Medikation">
        <MedicationList active={record.medications.active} discontinued={record.medications.discontinued} />
      </Card>

      <Card title="Diagnosen">
        {record.diagnoses.length === 0 ? (
          <p className="text-muted-foreground">Keine Diagnosen erfasst.</p>
        ) : (
          <ul className="flex flex-col divide-y">
            {record.diagnoses.map((diagnosis) => (
              <li key={diagnosis.id} className="flex flex-col gap-1 py-2">
                <span className="font-medium">{diagnosis.text}</span>
                <Provenance provenance={diagnosis.provenance} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Wiedervorlagen">
        <FollowUpList residentId={resident.id} followUps={record.follow_ups} />
      </Card>

      <Card title="Dokumente">
        {record.documents.length === 0 ? (
          <p className="text-muted-foreground">Noch keine freigegebenen Dokumente.</p>
        ) : (
          <ul className="flex flex-col divide-y">
            {record.documents.map((document) => (
              <li key={document.id} className="flex flex-wrap justify-between gap-2 py-2">
                {/* F04-AC10: the original in the browser's viewer, through the BFF. */}
                <a
                  href={`/api/documents/${encodeURIComponent(document.id)}/file`}
                  target="_blank"
                  rel="noopener"
                  className="underline"
                >
                  {(document.doc_type && DOC_TYPE_LABELS[document.doc_type]) || "Dokument"}
                  {document.document_date ? ` vom ${formatDate(document.document_date)}` : ""}
                </a>
                <span className="text-muted-foreground text-sm">
                  freigegeben
                  {document.approved_by_name ? ` von ${document.approved_by_name}` : ""}
                  {document.approved_at ? ` am ${formatDay(document.approved_at)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
