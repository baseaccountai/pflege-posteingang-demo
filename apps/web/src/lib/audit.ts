// The audit log for the PDL (F12): who did what with AI, human or agent. The API only
// answers the PDL (and RLS shows only her wards); here the events get their German words.
// No server code here: the client list uses this module, too.
import { LAYER_LABELS } from "@/components/attack-findings";

import { STATUS_LABELS } from "./documents/labels";
import { toolLabel } from "./agent";

export type AuditEvent = {
  id: number;
  at: string;
  ward_id: string | null;
  action: string;
  outcome: "ok" | "blocked" | "error";
  actor_type: "human" | "agent";
  actor_name: string;
  on_behalf_of_name: string | null;
  model: string | null;
  document_id: string | null;
  resident_id: string | null;
  resident_name: string | null;
  details: Record<string, unknown>;
};

export type AuditPage = { events: AuditEvent[]; next_before: number | null };
export type AuditFilters = { before?: number; agentOnly?: boolean; blockedOnly?: boolean };

const ACTION_LABELS: Record<string, string> = {
  upload: "Upload",
  status_change: "Statuswechsel",
  approval: "Freigabe",
  rejection: "Ablehnung",
  record_entry: "Akteneintrag",
  ocr: "Texterkennung (OCR)",
  screening: "Sicherheitsprüfung",
  extraction: "Feldvorschlag",
  question: "Frage",
  agent_task: "Agent-Auftrag",
  agent_tool: "Agent-Werkzeug",
  agent_proposal: "Vorschlag des Agenten",
  proposal_confirmed: "Vorschlag bestätigt",
  proposal_dismissed: "Vorschlag verworfen",
  blocked: "Blockiert",
  quota_exhausted: "Kontingent erschöpft",
};

const OUTCOME_LABELS: Record<AuditEvent["outcome"], string> = { ok: "ok", blocked: "blockiert", error: "Fehler" };

const ENTRY_LABELS: Record<string, string> = {
  medication: "Medikation",
  diagnosis: "Diagnose",
  follow_up: "Wiedervorlage",
};

const DETAIL_LABELS: Record<string, [string, (value: unknown) => string]> = {
  layer: ["Schicht", (v) => LAYER_LABELS[v as keyof typeof LAYER_LABELS] ?? String(v)],
  rule_id: ["Regel", String],
  tool: ["Werkzeug", (v) => toolLabel(String(v))],
  error_code: ["Fehlercode", String],
  proposal_id: ["Vorschlag", String],
  pages: ["Seiten", (v) => (Array.isArray(v) ? v.join(", ") : String(v))],
  status: ["Status", (v) => STATUS_LABELS[String(v)] ?? String(v)],
  entry: ["Eintrag", (v) => ENTRY_LABELS[String(v)] ?? String(v)],
};

/** The query of one page: the cursor and only the filters that are on. */
export function auditQuery({ before, agentOnly, blockedOnly }: AuditFilters): string {
  const params = new URLSearchParams();
  if (before !== undefined) params.set("before", String(before));
  if (agentOnly) params.set("agent_only", "true");
  if (blockedOnly) params.set("blocked_only", "true");
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** F12-AC2: action, outcome, actor ("KI-Agent im Auftrag von …") and details in German. */
export function describeEvent(event: AuditEvent) {
  return {
    action: ACTION_LABELS[event.action] ?? event.action,
    outcome: OUTCOME_LABELS[event.outcome] ?? event.outcome,
    actor:
      event.actor_type === "agent" && event.on_behalf_of_name
        ? `${event.actor_name} im Auftrag von ${event.on_behalf_of_name}`
        : event.actor_name,
    details: Object.entries(event.details).map(([key, value]) => {
      const [label, format] = DETAIL_LABELS[key] ?? [key, String];
      return `${label}: ${format(value)}`;
    }),
  };
}

