// F08 end to end (fake LLM with fixed rules, agent token in the fallback way self_signed):
// a proposal is only saved after "Bestätigen" (AC5, AC6) and then shows in the record as
// created by the agent; the tools used and what the agent cannot do are shown (AC11);
// another ward gives the same answer as nobody (AC10); /projekt names the token way (AC2).
import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

import { admin, loginAs, uniqueUser } from "./support/auth";

/** A fresh WB1 resident of its own, so parallel tests do not see each other's proposals. */
async function resident() {
  const id = randomUUID();
  const name = `Fr. Agent-T${id.slice(0, 6).toUpperCase()}`;
  await admin`insert into public.residents (id, ward_id, display_name, room) values (${id}, 'wb1', ${name}, '130')`;
  return { id, name };
}

async function openAgent(page: Page) {
  await page.goto("/fragen");
  await page.getByRole("navigation", { name: "Ansicht" }).getByRole("link", { name: "Agent" }).click();
  await page.waitForURL("/fragen?modus=agent");
}

async function order(page: Page, task: string, residentId?: string) {
  if (residentId) await page.getByLabel("Bewohner").selectOption(residentId);
  await page.getByLabel("Auftrag").fill(task);
  await page.getByRole("button", { name: "Auftrag geben" }).click();
}

test("a confirmed proposal becomes a follow-up of the agent in the record", async ({ page }) => {
  const person = await resident();
  const title = `Blutdruck messen ${randomUUID().slice(0, 6)}`;
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await openAgent(page);
  await expect(page.getByRole("list", { name: "Das kann der Agent nicht" })).toContainText("Medikation ändern");

  await order(page, `Wiedervorlage: ${title}`, person.id);
  const reply = page.getByTestId("agent-answer-0");
  await expect(reply).toContainText("Ich habe eine Wiedervorlage vorgeschlagen");
  await expect(reply).toContainText("Agent nutzte: Wiedervorlage vorschlagen");
  const card = reply.locator("[data-testid^=proposal-]");
  await expect(card).toContainText(person.name);
  await expect(card).toContainText(title);
  await expect(card).toContainText("Noch nicht gespeichert");

  // Not in the record before the nurse confirms (AC5).
  const [{ before }] = await admin<{ before: number }[]>`
    select count(*)::int as before from public.follow_ups where resident_id = ${person.id}`;
  expect(before).toBe(0);

  await card.getByRole("button", { name: "Bestätigen" }).click();
  await expect(card).toContainText("Bestätigt – Wiedervorlage in der Akte angelegt.");

  await page.goto(`/bewohner/${person.id}`);
  const followUps = page.getByRole("region", { name: "Wiedervorlagen" });
  await expect(followUps).toContainText(title);
  await expect(followUps).toContainText("vom Agenten angelegt · bestätigt von");
});

test("a dismissed proposal leaves the record unchanged", async ({ page }) => {
  const person = await resident();
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await openAgent(page);
  await order(page, "Wiedervorlage: Gewicht kontrollieren", person.id);
  const card = page.getByTestId("agent-answer-0").locator("[data-testid^=proposal-]");
  await card.getByRole("button", { name: "Verwerfen" }).click();
  await expect(card).toContainText("Verworfen – nichts gespeichert.");
  const [{ count }] = await admin<{ count: number }[]>`
    select count(*)::int as count from public.follow_ups where resident_id = ${person.id}`;
  expect(count).toBe(0);
});

test("the agent refuses what it cannot do and offers a proposal instead (AC8)", async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await openAgent(page);
  await order(page, "Ändere die Dosis von Ramipril auf 10 mg.");
  const reply = page.getByTestId("agent-answer-0");
  await expect(reply).toContainText("Das kann ich nicht");
  await expect(reply).toContainText("Dosis mit Hausarzt klären");
  await expect(reply).not.toContainText("Agent nutzte");
});

test("another ward gives the same answer as nobody (AC10)", async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await openAgent(page);
  const same = "Dazu gibt es in deinem Wohnbereich nichts – der Agent hat dieselben Rechte wie du.";
  await order(page, "Was steht in der Akte von Fr. Testfeld?"); // WB2
  await expect(page.getByTestId("agent-answer-0")).toContainText(same);
  await order(page, "Was steht in der Akte von Fr. Niemand?"); // nobody
  await expect(page.getByTestId("agent-answer-1")).toContainText(same);
});

test("the project page names the way of the agent token (AC2)", async ({ page }) => {
  await page.goto("/projekt");
  await expect(page.getByTestId("agent-token-way")).toContainText("Rückfall: Die API stellt das Agenten-Token selbst aus");
});
