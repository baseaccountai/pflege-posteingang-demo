// Texts of the inbox (F02-AC7, F02-AC8, F02-AC13). One place, so UI and tests agree.

export const STATUS_LABELS: Record<string, string> = {
  uploaded: "wartet",
  processing: "in Bearbeitung",
  extracting: "in Bearbeitung",
  ready_for_review: "bereit zur Prüfung",
  approved: "freigegeben",
  rejected: "verworfen",
  unreadable: "nicht lesbar",
  failed: "Fehler",
};

export const DOC_TYPE_LABELS: Record<string, string> = {
  arztbrief: "Arztbrief",
  medikationsplan: "Medikationsplan",
  ueberleitungsbogen: "Überleitungsbogen",
  sonstiges: "Sonstiges",
};

export const DAILY_QUOTA_MESSAGE =
  "Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter.";

const ERROR_MESSAGES: Record<string, string> = {
  unreadable_text: "Dokument nicht lesbar – bitte neu fotografieren (gerade, hell, ganze Seite)",
  not_care_document: "Kein Pflegedokument erkannt",
  ocr_unavailable: "Texterkennung gerade nicht erreichbar – bitte erneut versuchen.",
  llm_unavailable: "KI-Vorschlag gerade nicht erreichbar – bitte erneut versuchen.",
  quota_exceeded: DAILY_QUOTA_MESSAGE,
  timeout: "Verarbeitung hat zu lange gedauert – bitte erneut versuchen.",
};

/** Running steps: the inbox keeps polling while one of these is shown (F02-AC6). */
export function isPending(status: string): boolean {
  return status === "uploaded" || status === "processing" || status === "extracting";
}

export function errorMessage(code: string | null): string | null {
  if (!code) return null;
  return ERROR_MESSAGES[code] ?? "Unbekannter Fehler – bitte erneut versuchen.";
}
