// F05 end to end (fake OCR, LLM and embeddings): a not yet searchable document is indexed
// from the record (AC1a), a question from the record's link is answered with a source
// (AC5, AC8, AC10), a role switch leaves no conversation behind (AC11).
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

import { admin, loginAs, signInAtMockIdp, uniqueUser } from "./support/auth";
import { MOCK_OIDC_ISSUER } from "./support/env";
import { sample } from "./support/inbox";

const TEXT = "# Arztbrief\n## Medikation\nRamipril 5 mg morgens gegen Bluthochdruck";
const QUESTION = "Medikation Ramipril morgens?";

/** A WB1 resident with an approved letter whose indexing failed. */
async function residentWithLetter() {
  const id = randomUUID();
  const name = `Fr. Frage-${id.slice(0, 6)}`;
  await admin`insert into public.residents (id, ward_id, display_name, room) values (${id}, 'wb1', ${name}, '120')`;
  const pdf = readFileSync(sample("arztbrief_muster-bauer.pdf"));
  const [{ doc }] = await admin<{ doc: string }[]>`
    insert into public.documents (ward_id, resident_id, uploaded_by, upload_session, status,
      doc_type, document_date, ocr_pages, approved_by, approved_by_name, approved_at, indexing_status)
    values ('wb1', ${id}, 'seed', 'seed', 'approved', 'arztbrief', '2026-10-20',
      ${admin.json([{ page: 1, markdown: TEXT }])}, 'seed', 'Pflegekraft WB1', now(), 'failed')
    returning id::text as doc`;
  await admin`insert into public.document_files (document_id, ward_id, mime, size_bytes, content)
    values (${doc}, 'wb1', 'application/pdf', ${pdf.length}, ${pdf})`;
  return { id, name, doc };
}

async function switchToWb2(page: Page) {
  await page.goto("/");
  const authorize = page.waitForRequest((r) => r.url().startsWith(`${MOCK_OIDC_ISSUER}/authorize`));
  await page
    .getByRole("group", { name: "Pflegekraft WB2" })
    .getByRole("button", { name: "Als Pflegekraft WB2 anmelden" })
    .click();
  await authorize;
}

test("index from the record, then ask about the resident and open the source", async ({ page }) => {
  const resident = await residentWithLetter();
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto(`/bewohner/${resident.id}`);
  const documents = page.getByRole("region", { name: "Dokumente" });
  await expect(documents).toContainText("noch nicht durchsuchbar");
  await documents.getByRole("button", { name: "Erneut versuchen" }).click();
  await page.waitForURL(`/bewohner/${resident.id}`);
  await expect(documents).not.toContainText("noch nicht durchsuchbar");

  await page.getByRole("link", { name: "Fragen zu diesem Bewohner" }).click();
  await page.waitForURL(`/fragen?bewohner=${resident.id}`);
  await expect(page.getByLabel("Bewohner")).toHaveValue(resident.id);
  await page.getByLabel("Frage").fill(QUESTION);
  await page.getByRole("button", { name: "Fragen" }).click();

  const answer = page.getByTestId("answer-0");
  await expect(answer).toContainText("Ramipril 5 mg morgens gegen Bluthochdruck [Q1]");
  await expect(answer).toContainText("Antwort von fake-llm (Testattrappe)");
  const source = answer.getByRole("link", { name: new RegExp(`Arztbrief vom 20.10.2026 · ${resident.name} · Seite 1`) });
  const file = await page.request.get((await source.getAttribute("href"))!);
  expect(file.status()).toBe(200);
  expect(file.headers()["content-type"]).toContain("application/pdf");

  // F06-AC5, AC7: asked by name, the model got only the resident's code.
  await page.getByLabel("Frage").fill(`${QUESTION} Wie bei ${resident.name}?`);
  await page.getByRole("button", { name: "Fragen" }).click();
  const second = page.getByTestId("answer-1");
  await second.getByText("Das hat das KI-Modell gesehen").click();
  const seen = second.locator("details");
  await expect(seen).toContainText(/Frage: .*Bewohner_[A-Z]\d{2}/);
  await expect(seen).not.toContainText(resident.name.split(" ")[1]);
});

test("after a role switch the conversation is gone and WB1 is not found", async ({ page }) => {
  const resident = await residentWithLetter();
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto(`/bewohner/${resident.id}`);
  const documents = page.getByRole("region", { name: "Dokumente" });
  await documents.getByRole("button", { name: "Erneut versuchen" }).click();
  // The reload goes to the same URL, so wait for its content, not for the URL.
  await expect(documents).not.toContainText("noch nicht durchsuchbar");
  await page.goto("/fragen");
  await page.getByLabel("Frage").fill(QUESTION);
  await page.getByRole("button", { name: "Fragen" }).click();
  await expect(page.getByTestId("answer-0")).toContainText("[Q1]");

  await switchToWb2(page);
  await signInAtMockIdp(page, uniqueUser("pflege-wb2"), ["nurse_wb2"]);
  await page.waitForURL("/");
  await page.goto("/fragen");
  await expect(page.getByTestId("answer-0")).toHaveCount(0);
  await page.getByLabel("Frage").fill(`${QUESTION} ${resident.name}`);
  await page.getByRole("button", { name: "Fragen" }).click();
  await expect(page.getByTestId("answer-0")).toContainText("Keine Treffer in deinem Wohnbereich.");
});

test("an answer that arrives after a role switch in another tab is never shown", async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto("/fragen");
  // Hold the question until the other tab has switched the role.
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route("**/api/questions", async (route) => {
    await held;
    await route.continue();
  });
  await page.getByLabel("Frage").fill(QUESTION);
  await page.getByRole("button", { name: "Fragen" }).click();

  const otherTab = await page.context().newPage();
  await switchToWb2(otherTab);
  await page.waitForURL("/"); // the asking tab is sent away (session sync)
  release();
  await expect(page.locator("body")).not.toContainText("[Q1]");
  await expect(page.getByTestId("answer-0")).toHaveCount(0);
});
