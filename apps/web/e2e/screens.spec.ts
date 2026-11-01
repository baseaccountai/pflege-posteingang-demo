// Phase 9: screenshots for the project description (docs/assets/projekt/). Not a test of
// its own - it runs only with SCREENS=1 (make screens), on the local e2e stack with the
// sample data of the seed and the fake models, so it costs nothing and touches no public
// data. The pictures say so in their caption.
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

import { admin, loginAs, uniqueUser } from "./support/auth";
import { WB1_RESIDENT } from "./support/env";
import { row, sample, upload } from "./support/inbox";

test.skip(!process.env.SCREENS, "only for make screens");
test.describe.configure({ mode: "serial" });

const OUT = path.resolve(__dirname, "../../../docs/assets/projekt");
const shot = (page: Page, name: string, fullPage = false) =>
  page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage, animations: "disabled" });

// The fake embeddings find a text only through shared words, so question and letter share some.
const TEXT = "# Arztbrief\n## Medikation\nRamipril 5 mg morgens nehmen. Blutdruck wöchentlich kontrollieren.";
const QUESTION = "Wann soll Hr. Muster-Bauer Ramipril nehmen, und wie oft Blutdruck kontrollieren?";

/** An approved letter of Hr. Muster-Bauer that is not yet searchable (indexed from the record). */
async function letterToIndex() {
  const pdf = readFileSync(sample("arztbrief_muster-bauer.pdf"));
  const [{ doc }] = await admin<{ doc: string }[]>`
    insert into public.documents (ward_id, resident_id, uploaded_by, upload_session, status,
      doc_type, document_date, ocr_pages, screened_pages, screening_result,
      approved_by, approved_by_name, approved_at, indexing_status)
    values ('wb1', ${WB1_RESIDENT.id}, 'seed', 'seed', 'approved', 'arztbrief', '2026-10-20',
      ${admin.json([{ page: 1, markdown: TEXT }])}, ${admin.json([{ page: 1, markdown: TEXT }])}, 'clean',
      'seed', 'Pflegekraft WB1', now(), 'failed')
    returning id::text as doc`;
  await admin`insert into public.document_files (document_id, ward_id, mime, size_bytes, content)
    values (${doc}, 'wb1', 'application/pdf', ${pdf.length}, ${pdf})`;
}

test("desktop screens", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop");
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1280, height: 900 });

  await page.goto("/");
  await shot(page, "start");

  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto("/posteingang");
  const plan = await upload(page, "Datei hochladen", sample("medikationsplan_muster-bauer.pdf"));
  const attack = await upload(page, "Datei hochladen", sample("angriff_versteckt_probe.pdf"));
  await expect(row(page, plan)).toContainText("bereit zur Prüfung", { timeout: 20_000 });
  await expect(row(page, attack)).toContainText("verdächtig", { timeout: 20_000 });
  await shot(page, "posteingang");

  await row(page, attack).getByRole("link", { name: "Prüfen" }).click();
  await expect(page.getByRole("region", { name: "Angriff erkannt" })).toContainText("Versteckter Text");
  // Only the finding: headless Chromium shows no PDF, so the original's frame stays empty.
  await page.getByRole("region", { name: "Angriff erkannt" }).screenshot({ path: path.join(OUT, "angriff-erkannt.png") });

  await page.goto("/posteingang");
  await row(page, plan).getByRole("link", { name: "Prüfen" }).click();
  const comparison = page.getByRole("list", { name: "Medikationsabgleich" });
  await expect(comparison).toContainText("neu");
  // The proposal column from the resident down to the comparison with the record.
  const from = (await page.getByLabel("Bewohner", { exact: true }).boundingBox())!;
  const to = (await comparison.boundingBox())!;
  await page.screenshot({
    path: path.join(OUT, "pruefen.png"),
    fullPage: true,
    clip: { x: from.x - 30, y: from.y - 60, width: from.width + 60, height: to.y + to.height - from.y + 80 },
  });

  await letterToIndex();
  await page.goto(`/bewohner/${WB1_RESIDENT.id}`);
  const documents = page.getByRole("region", { name: "Dokumente" });
  await documents.getByRole("button", { name: "Erneut versuchen" }).click();
  await expect(documents).not.toContainText("noch nicht durchsuchbar");
  await shot(page, "bewohnerakte");

  await page.getByRole("link", { name: "Fragen zu diesem Bewohner" }).click();
  await page.getByLabel("Frage").fill(QUESTION);
  await page.getByRole("button", { name: "Fragen" }).click();
  await expect(page.getByTestId("answer-0")).toContainText("[Q1]");
  await page.getByTestId("answer-0").getByText("Das hat das KI-Modell gesehen").click();
  await shot(page, "fragen");

  await page.goto(`/fragen?modus=agent&bewohner=${WB1_RESIDENT.id}`);
  await page.getByLabel("Auftrag").fill(`Wiedervorlage: Blutdruck messen ${randomUUID().slice(0, 4)}`);
  await page.getByRole("button", { name: "Auftrag geben" }).click();
  await expect(page.getByTestId("agent-answer-0")).toContainText("Agent nutzte");
  await shot(page, "agent");

  // Another ward: the WB1 record does not exist for WB2 - also not for its agent.
  await page.context().clearCookies(); // a running session ignores a plain login link
  await loginAs(page, "wb2", uniqueUser("pflege-wb2"), ["nurse_wb2"]);
  await page.goto(`/bewohner/${WB1_RESIDENT.id}`);
  await expect(page.getByRole("heading", { name: "Nicht gefunden oder kein Zugriff" })).toBeVisible();
  await shot(page, "kein-zugriff");
});

test("phone screens", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile");
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto(`/bewohner/${WB1_RESIDENT.id}`);
  await expect(page.getByRole("region", { name: "Wiedervorlagen" })).toBeVisible();
  await shot(page, "handy-bewohnerakte");
});
