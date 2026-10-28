// F10-AC7, AC12, AC13 against the API stand-in (e2e/support/api-stub.mjs) behind a second
// app instance: start-up notice with retry and sample record link, quota and maintenance
// messages. Login happens on the normal instance; the session cookie also holds there.
import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

import { loginAs, uniqueUser } from "./support/auth";
import { STUB_APP_ORIGIN } from "./support/env";

const STARTING = "Demo startet gerade … (bis zu 30 Sekunden)";
const residentId = (prefix: string) => `${prefix}-${randomUUID().slice(9)}`;

async function openOnStub(page: Page, path: string) {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto(`${STUB_APP_ORIGIN}${path}`);
}

test("an API slower than 5 s gives the start-up notice with the sample record link (AC13)", async ({ page }) => {
  await openOnStub(page, `/bewohner/${residentId("51000000")}`);
  await expect(page.getByText(STARTING)).toBeVisible({ timeout: 10_000 });
  await page.getByRole("link", { name: "Musterakte ansehen" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Fr. Beispiel" })).toBeVisible();
});

test("after a 503 the page reloads by itself once the API is ready (AC13)", async ({ page }) => {
  await openOnStub(page, `/bewohner/${residentId("50300000")}`);
  await expect(page.getByText(STARTING)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "Fr. Attrappe" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(STARTING)).toHaveCount(0);
});

test("a used-up daily quota is explained at the upload; the inbox stays usable (AC12)", async ({ page }) => {
  await openOnStub(page, "/posteingang");
  await expect(page.getByLabel("Datei hochladen")).toBeEnabled();
  await page.getByLabel("Datei hochladen").setInputFiles({
    name: "plan.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 Muster"),
  });
  await expect(
    page.getByText("Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter."),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Posteingang" })).toBeVisible();
});

test("a write during the nightly reset shows the maintenance message (AC7)", async ({ page }) => {
  await openOnStub(page, `/bewohner/${residentId("00000000")}`);
  await page.getByRole("button", { name: "Blutdruck messen als erledigt markieren" }).click();
  await expect(
    page.getByText("Demo wird gerade zurückgesetzt – bitte in einer Minute erneut versuchen"),
  ).toBeVisible();
});
