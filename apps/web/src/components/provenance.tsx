// F04-AC5, AC6: where an entry of the record came from and who confirmed it - one line,
// e.g. "Arztbrief vom 12.10.2026 · freigegeben von Pflegekraft WB1 am 24.10.2026".
import { formatDate, formatDay } from "@/lib/dates";
import { DOC_TYPE_LABELS } from "@/lib/documents/labels";

export type ProvenanceData = {
  document_id: string | null;
  doc_type: string | null;
  document_date: string | null;
  actor_type: "human" | "agent" | string;
  confirmed_by_name: string;
  confirmed_at: string;
};

export function Provenance({ provenance }: { provenance: ProvenanceData | null }) {
  if (!provenance) {
    return (
      <p data-testid="provenance" className="text-muted-foreground text-xs">
        Herkunft unbekannt
      </p>
    );
  }
  const confirmed = `${provenance.confirmed_by_name} am ${formatDay(provenance.confirmed_at)}`;
  return (
    <p data-testid="provenance" className="text-muted-foreground text-xs">
      <DocumentLink provenance={provenance} />
      {" · "}
      {provenance.actor_type === "agent"
        ? `vom Agenten angelegt · bestätigt von ${confirmed}`
        : `freigegeben von ${confirmed}`}
    </p>
  );
}

function DocumentLink({ provenance }: { provenance: ProvenanceData }) {
  if (!provenance.document_id) return <>ohne Herkunftsdokument</>;
  const type = (provenance.doc_type && DOC_TYPE_LABELS[provenance.doc_type]) || "Dokument";
  const date = provenance.document_date ? ` vom ${formatDate(provenance.document_date)}` : "";
  return (
    // The original opens in the browser's own viewer (PDF/image) via the BFF (F04-AC10).
    <a
      href={`/api/documents/${encodeURIComponent(provenance.document_id)}/file`}
      target="_blank"
      rel="noopener"
      className="underline"
    >
      {type}
      {date}
    </a>
  );
}
