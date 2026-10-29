// Screen 5 "Angriff erkannt" (F07-AC6): what the injection check found in this document and
// what the protection did. Excerpts are document text: shown as plain text, never as markup.
export type Finding = {
  page: number;
  invisible: boolean; // hidden text the OCR did not read
  layer: "hidden_text" | "pattern" | "classifier";
  rule_id: string;
  category: string;
  excerpt: string;
  explanation: string;
};

const LAYER_LABELS: Record<Finding["layer"], string> = {
  hidden_text: "Versteckter Text",
  pattern: "Regel",
  classifier: "Prüfmodell",
};

export function AttackFindings({ findings }: { findings: Finding[] }) {
  return (
    <section aria-labelledby="attack-heading" className="flex flex-col gap-3 rounded-lg border border-red-300 bg-red-50 p-4 text-red-950">
      <h2 id="attack-heading" className="text-lg font-semibold">
        Angriff erkannt
      </h2>
      <p className="text-sm">
        Dieses Dokument enthält Anweisungen an die KI. Die betroffenen Abschnitte wurden nicht an die KI
        weitergegeben und sind nicht durchsuchbar. Die übrigen Angaben können Sie wie gewohnt prüfen; ohne Ihre
        Freigabe gelangt nichts in die Akte.
      </p>
      <ul className="flex flex-col gap-2">
        {findings.map((finding, index) => (
          <li key={index} className="flex flex-col gap-1 rounded-md border border-red-200 bg-white p-3 text-sm">
            <span className="font-medium">
              {LAYER_LABELS[finding.layer] ?? finding.layer} · Seite {finding.page}
              {finding.invisible && (
                <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-xs">im Dokument unsichtbar</span>
              )}
            </span>
            <blockquote className="border-l-4 border-red-300 pl-2 font-mono text-xs whitespace-pre-line">
              {finding.excerpt}
            </blockquote>
            <span className="text-muted-foreground text-xs">{finding.explanation}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
