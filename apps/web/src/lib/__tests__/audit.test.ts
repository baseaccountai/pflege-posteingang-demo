// F12-AC2, AC7: what an event says in the app, and the query of a page of the log.
import { describe, expect, it } from "vitest";

import { auditQuery, describeEvent, type AuditEvent } from "@/lib/audit";

const EVENT: AuditEvent = {
  id: 7,
  at: "2026-10-30T13:05:09+00:00",
  ward_id: "wb1",
  action: "blocked",
  outcome: "blocked",
  actor_type: "human",
  actor_name: "Pflegekraft WB1",
  on_behalf_of_name: null,
  model: null,
  document_id: "d1",
  resident_id: null,
  resident_name: null,
  details: { layer: "pattern", rule_id: "ignore-de", pages: [1, 2] },
};

describe("auditQuery", () => {
  it("passes only the filters that are on and the cursor", () => {
    expect(auditQuery({})).toBe("");
    expect(auditQuery({ agentOnly: true, blockedOnly: true, before: 42 })).toBe(
      "?before=42&agent_only=true&blocked_only=true",
    );
  });
});

describe("describeEvent", () => {
  it("names the action, the outcome and the details in German", () => {
    expect(describeEvent(EVENT)).toEqual({
      action: "Blockiert",
      outcome: "blockiert",
      actor: "Pflegekraft WB1",
      details: ["Schicht: Regel", "Regel: ignore-de", "Seiten: 1, 2"],
    });
  });

  it("names the agent and the user it works for", () => {
    const agent = { ...EVENT, actor_type: "agent" as const, actor_name: "KI-Agent", on_behalf_of_name: "Pflegekraft WB1" };
    expect(describeEvent(agent).actor).toBe("KI-Agent im Auftrag von Pflegekraft WB1");
  });

  it("names the agent's proposals, decisions and tools (F08)", () => {
    const agent = { ...EVENT, actor_type: "agent" as const, outcome: "ok" as const };
    expect(describeEvent({ ...agent, action: "agent_proposal", details: {} }).action).toBe("Vorschlag des Agenten");
    expect(describeEvent({ ...EVENT, action: "proposal_confirmed", details: {} }).action).toBe("Vorschlag bestätigt");
    expect(describeEvent({ ...EVENT, action: "proposal_dismissed", details: {} }).action).toBe("Vorschlag verworfen");
    expect(describeEvent({ ...agent, action: "agent_tool", details: { tool: "medikation_abgleichen" } })).toMatchObject({
      action: "Agent-Werkzeug",
      details: ["Werkzeug: Medikationsabgleich"],
    });
  });

  it("translates states and record entries, and keeps unknown values readable", () => {
    const change = { ...EVENT, action: "status_change", outcome: "error" as const, details: { status: "failed", error_code: "llm_unavailable" } };
    expect(describeEvent(change)).toMatchObject({
      action: "Statuswechsel",
      outcome: "Fehler",
      details: ["Status: Fehler", "Fehlercode: llm_unavailable"],
    });
    const entry = { ...EVENT, action: "record_entry", outcome: "ok" as const, details: { entry: "follow_up" } };
    expect(describeEvent(entry)).toMatchObject({ action: "Akteneintrag", outcome: "ok", details: ["Eintrag: Wiedervorlage"] });
    expect(describeEvent({ ...EVENT, action: "new_thing", details: { other: "x" } })).toMatchObject({
      action: "new_thing",
      details: ["other: x"],
    });
  });
});
