// F04-AC4, AC5: medications of the record. Active ones with dosage and "neu"/"geändert",
// stopped ones (last 30 days) struck through, each with the origin of its latest change
// and the whole history to unfold.
import { Provenance, type ProvenanceData } from "@/components/provenance";
import { formatDate, formatDay } from "@/lib/dates";
import { DOC_TYPE_LABELS } from "@/lib/documents/labels";
import type { Dosage, MedicationEvent, MedicationSide, RecordMedication } from "@/lib/residents";

/** "1-0-1-0": morning, noon, evening, night - the usual notation on German plans. */
export function dosageText(dosage: Dosage): string {
  return [dosage.morgens, dosage.mittags, dosage.abends, dosage.nachts].map((v) => v || "0").join("-");
}

const side = (s: MedicationSide) => [s.strength, dosageText(s.dosage), s.hint].filter(Boolean).join(", ");

function documentName(provenance: ProvenanceData | null): string {
  if (!provenance?.document_id) return "ohne Dokument";
  const type = (provenance.doc_type && DOC_TYPE_LABELS[provenance.doc_type]) || "Dokument";
  return provenance.document_date ? `${type} vom ${formatDate(provenance.document_date)}` : type;
}

export function MedicationList({
  active,
  discontinued,
  sample = false,
}: {
  active: RecordMedication[];
  discontinued: RecordMedication[];
  sample?: boolean;
}) {
  if (active.length === 0 && discontinued.length === 0) {
    return <p className="text-muted-foreground">Keine Medikation erfasst.</p>;
  }
  return (
    <ul className="flex flex-col divide-y">
      {active.map((med) => (
        <li key={med.id} data-testid={`medication-${med.id}`} className="flex flex-col gap-1 py-2">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{[med.name, med.strength].filter(Boolean).join(" ")}</span>
            <span className="font-mono text-sm">{dosageText(med.dosage)}</span>
            {med.hint && <span className="text-sm">· {med.hint}</span>}
            {med.marker === "new" && (
              <span className="rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-800">neu</span>
            )}
            {med.marker === "changed" && (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">
                geändert{med.previous ? ` (vorher: ${side(med.previous)})` : ""}
              </span>
            )}
          </span>
          <Provenance provenance={med.provenance} sample={sample} />
          <History events={med.events} sample={sample} />
        </li>
      ))}
      {discontinued.map((med) => (
        <li key={med.id} data-testid={`medication-${med.id}`} className="flex flex-col gap-1 py-2">
          <span className="text-muted-foreground flex flex-wrap items-center gap-2">
            <s>{[med.name, med.strength].filter(Boolean).join(" ")}</s>
            <span className="text-sm">
              abgesetzt am {med.discontinued_at ? formatDay(med.discontinued_at) : "?"} laut{" "}
              {documentName(med.provenance)}
            </span>
          </span>
          <Provenance provenance={med.provenance} sample={sample} />
          <History events={med.events} sample={sample} />
        </li>
      ))}
    </ul>
  );
}

const KIND = { new: "angesetzt", changed: "geändert", discontinued: "abgesetzt" } as const;

function History({ events, sample }: { events: MedicationEvent[]; sample: boolean }) {
  if (events.length === 0) return null;
  return (
    <details className="text-sm">
      <summary className="cursor-pointer">Verlauf ({events.length})</summary>
      <ol className="mt-1 flex flex-col gap-1 border-l pl-3">
        {events.map((event, index) => (
          <li key={index}>
            {KIND[event.kind]}
            {event.kind === "new" && event.after && `: ${side(event.after)}`}
            {event.kind === "changed" &&
              event.before &&
              event.after &&
              `: ${side(event.before)} → ${side(event.after)}`}
            <Provenance provenance={event.provenance} sample={sample} />
          </li>
        ))}
      </ol>
    </details>
  );
}
