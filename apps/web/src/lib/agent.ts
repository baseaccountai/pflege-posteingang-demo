// The agent (F08) in the app's words: its tools and what it cannot do (AC11).

const TOOL_LABELS: Record<string, string> = {
  dokumente_durchsuchen: "Dokumentsuche",
  bewohnerakte_lesen: "Bewohnerakte lesen",
  medikation_abgleichen: "Medikationsabgleich",
  wiedervorlagen_auflisten: "Wiedervorlagen auflisten",
  wiedervorlage_vorschlagen: "Wiedervorlage vorschlagen",
};

// Not a promise of the prompt: the API has no such tool, and RLS refuses these writes.
export const AGENT_CANNOT = ["Medikation ändern", "Daten löschen", "Nachrichten senden", "andere Wohnbereiche lesen"];

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool;
}

/** "Agent nutzte: Medikationsabgleich, Wiedervorlage vorschlagen" - or null without tools. */
export function toolsUsedLine(tools: string[]): string | null {
  return tools.length ? `Agent nutzte: ${tools.map(toolLabel).join(", ")}` : null;
}
