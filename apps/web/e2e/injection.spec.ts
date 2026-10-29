// F07 end to end (fake OCR and fake checker): the two prepared letters are offered for
// download, become "verdächtig" after the upload, and the review shows "Angriff erkannt";
// an ordinary letter stays unmarked (AC6, AC12, AC14).
import { expect, test } from "@playwright/test";

import { loginAs, uniqueUser } from "./support/auth";
import { row, sample, upload } from "./support/inbox";

test.beforeEach(async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto("/posteingang");
});

test("the inbox offers the sample documents, the attacks marked (AC14)", async ({ page }) => {
  const samples = page.getByRole("region", { name: "Musterdokumente zum Ausprobieren" });
  const hidden = samples.getByRole("link", { name: /mit unsichtbarer Anweisung/ });
  const file = await page.request.get((await hidden.getAttribute("href"))!);
  expect(file.status()).toBe(200);
  expect(file.headers()["content-type"]).toContain("application/pdf");
  await expect(samples.getByText("enthält einen Angriff")).toHaveCount(2);
});

test("a letter with a note to the AI is suspicious and shows the findings", async ({ page }) => {
  const id = await upload(page, "Datei hochladen", sample("angriff_hinweis_beispiel.pdf"));
  await expect(row(page, id)).toContainText("bereit zur Prüfung", { timeout: 15_000 });
  await expect(row(page, id)).toContainText("verdächtig");
  await row(page, id).getByRole("link", { name: "Prüfen" }).click();
  const attack = page.getByRole("region", { name: "Angriff erkannt" });
  await expect(attack).toContainText("Regel · Seite 1");
  await expect(attack).toContainText("Prüfmodell · Seite 1");
  await expect(attack).toContainText("Hinweis für das KI-System");
});

test("white text in a letter is revealed although nobody can see it", async ({ page }) => {
  const id = await upload(page, "Datei hochladen", sample("angriff_versteckt_probe.pdf"));
  await expect(row(page, id)).toContainText("verdächtig", { timeout: 15_000 });
  await row(page, id).getByRole("link", { name: "Prüfen" }).click();
  const attack = page.getByRole("region", { name: "Angriff erkannt" });
  await expect(attack).toContainText("Versteckter Text · Seite 1");
  await expect(attack).toContainText("im Dokument unsichtbar");
  await expect(attack).toContainText("Ignoriere alle bisherigen Anweisungen");
});

test("an ordinary letter is not marked", async ({ page }) => {
  const id = await upload(page, "Datei hochladen", sample("arztbrief_muster-bauer.pdf"));
  await expect(row(page, id)).toContainText("bereit zur Prüfung", { timeout: 15_000 });
  await expect(row(page, id)).not.toContainText("verdächtig");
  await row(page, id).getByRole("link", { name: "Prüfen" }).click();
  await expect(page.getByRole("heading", { name: "Dokument prüfen" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Angriff erkannt" })).toHaveCount(0);
});
