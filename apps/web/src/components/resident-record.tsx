// Screen 7 (F04): the record, every entry with its origin. Used live on /bewohner/[id] and
// as the static sample record on /muster (F10-AC14): `sample` opens the originals as
// static files and leaves out everything that needs a login (questions, "erledigt").
import Link from "next/link";
import type { ReactNode } from "react";

import { FollowUpList } from "@/components/follow-up-list";
import { MedicationList } from "@/components/medication-list";
import { Provenance } from "@/components/provenance";
import { SearchState } from "@/components/search-state";
import { formatDate, formatDay } from "@/lib/dates";
import { fileHref } from "@/lib/documents/file-href";
import { DOC_TYPE_LABELS } from "@/lib/documents/labels";
import type { ResidentRecord } from "@/lib/residents";

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function ResidentRecordView({ record, sample = false }: { record: ResidentRecord; sample?: boolean }) {
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
        {!sample && (
          <Link
            href={`/fragen?bewohner=${encodeURIComponent(resident.id)}`}
            className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
          >
            Fragen zu diesem Bewohner
          </Link>
        )}
      </div>

      <Card title="Medikation">
        <MedicationList
          active={record.medications.active}
          discontinued={record.medications.discontinued}
          sample={sample}
        />
      </Card>

      <Card title="Diagnosen">
        {record.diagnoses.length === 0 ? (
          <p className="text-muted-foreground">Keine Diagnosen erfasst.</p>
        ) : (
          <ul className="flex flex-col divide-y">
            {record.diagnoses.map((diagnosis) => (
              <li key={diagnosis.id} className="flex flex-col gap-1 py-2">
                <span className="font-medium">{diagnosis.text}</span>
                <Provenance provenance={diagnosis.provenance} sample={sample} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Wiedervorlagen">
        <FollowUpList residentId={resident.id} followUps={record.follow_ups} sample={sample} />
      </Card>

      <Card title="Dokumente">
        {record.documents.length === 0 ? (
          <p className="text-muted-foreground">Noch keine freigegebenen Dokumente.</p>
        ) : (
          <ul className="flex flex-col divide-y">
            {record.documents.map((document) => (
              <li key={document.id} className="flex flex-wrap justify-between gap-2 py-2">
                {/* F04-AC10: the original in the browser's viewer, through the BFF. */}
                <a href={fileHref(document.id, sample)} target="_blank" rel="noopener" className="underline">
                  {(document.doc_type && DOC_TYPE_LABELS[document.doc_type]) || "Dokument"}
                  {document.document_date ? ` vom ${formatDate(document.document_date)}` : ""}
                </a>
                <span className="text-muted-foreground text-sm">
                  freigegeben
                  {document.approved_by_name ? ` von ${document.approved_by_name}` : ""}
                  {document.approved_at ? ` am ${formatDay(document.approved_at)}` : ""}
                </span>
                <SearchState
                  documentId={document.id}
                  residentId={resident.id}
                  status={document.indexing_status}
                  sample={sample}
                />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
