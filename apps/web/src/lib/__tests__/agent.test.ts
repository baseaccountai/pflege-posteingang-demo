// F08-AC11: which tools the agent used, in words a nurse understands.
import { describe, expect, it } from "vitest";

import { AGENT_CANNOT, toolLabel, toolsUsedLine } from "@/lib/agent";

describe("agent labels", () => {
  it("names every tool of the agent in German", () => {
    expect(toolLabel("dokumente_durchsuchen")).toBe("Dokumentsuche");
    expect(toolLabel("bewohnerakte_lesen")).toBe("Bewohnerakte lesen");
    expect(toolLabel("medikation_abgleichen")).toBe("Medikationsabgleich");
    expect(toolLabel("wiedervorlagen_auflisten")).toBe("Wiedervorlagen auflisten");
    expect(toolLabel("wiedervorlage_vorschlagen")).toBe("Wiedervorlage vorschlagen");
    expect(toolLabel("etwas_neues")).toBe("etwas_neues");
  });

  it("writes the line under an answer, or nothing without tools", () => {
    expect(toolsUsedLine(["medikation_abgleichen", "wiedervorlage_vorschlagen"])).toBe(
      "Agent nutzte: Medikationsabgleich, Wiedervorlage vorschlagen",
    );
    expect(toolsUsedLine([])).toBeNull();
  });

  it("lists what the agent cannot do", () => {
    expect(AGENT_CANNOT).toEqual(["Medikation ändern", "Daten löschen", "Nachrichten senden", "andere Wohnbereiche lesen"]);
  });
});
