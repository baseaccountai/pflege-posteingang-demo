// F10-AC4: banner and footer on every page type of the app, on desktop and phone, and no
// sideways scrolling on the phone. The IdP's login pages are not ours and are left out.
// Still to come with their features: Fragen (F05), /projekt (F09), Offline-Seite (F11).
import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

import { loginAs, uniqueUser } from "./support/auth";
import { STUB_APP_ORIGIN, WB1_RESIDENT, WB2_RESIDENT } from "./support/env";
import { row, sample, upload } from "./support/inbox";

const BANNER = "MUSTERDATEN · keine echten Personen";
const DISCLAIMER = "Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt";

async function expectFrame(page: Page) {
  await expect(page.getByText(BANNER, { exact: true })).toBeVisible();
  await expect(page.getByTestId("disclaimer")).toHaveText(DISCLAIMER);
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page wider than the screen").toBeLessThanOrEqual(0);
}

test.describe("without login", () => {
  const pages: [string, string, RegExp][] = [
    ["start page", "/", /Pflege-Posteingang/],
    ["sample record", "/muster", /Fr\. Beispiel/],
    ["login error", "/auth/error", /Anmeldung fehlgeschlagen/],
    ["unknown address (404)", "/gibt-es-nicht", /Seite nicht gefunden/],
  ];
  for (const [name, path, heading] of pages) {
    test(name, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await expectFrame(page);
    });
  }
});

test.describe("as WB1 nurse", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  });

  test("inbox and review", async ({ page }) => {
    await page.goto("/posteingang");
    await expect(page.getByRole("heading", { level: 1, name: "Posteingang" })).toBeVisible();
    await expectFrame(page);
    const id = await upload(page, "Datei hochladen", sample("medikationsplan_muster-bauer.pdf"));
    await expect(row(page, id)).toContainText("bereit zur Prüfung", { timeout: 15_000 });
    await page.goto(`/posteingang/${id}`);
    await expect(page.getByRole("heading", { level: 1, name: "Dokument prüfen" })).toBeVisible();
    await expectFrame(page);
  });

  test("resident list, record and no access", async ({ page }) => {
    await page.goto("/bewohner");
    await expect(page.getByRole("heading", { level: 1, name: "Bewohner" })).toBeVisible();
    await expectFrame(page);
    await page.goto(`/bewohner/${WB1_RESIDENT.id}`);
    await expect(page.getByRole("heading", { level: 1, name: WB1_RESIDENT.name })).toBeVisible();
    await expectFrame(page);
    await page.goto(`/bewohner/${WB2_RESIDENT.id}`);
    await expect(page.getByRole("heading", { level: 1, name: "Nicht gefunden oder kein Zugriff" })).toBeVisible();
    await expectFrame(page);
  });

  test("error page and start-up notice (API stand-in)", async ({ page }) => {
    await page.goto(`${STUB_APP_ORIGIN}/bewohner/50000000-${randomUUID().slice(9)}`);
    await expect(page.getByRole("heading", { level: 1, name: "Etwas ist schiefgelaufen" })).toBeVisible();
    await expectFrame(page);
    await page.goto(`${STUB_APP_ORIGIN}/bewohner/50300000-${randomUUID().slice(9)}`);
    await expect(page.getByText("Demo startet gerade … (bis zu 30 Sekunden)")).toBeVisible();
    await expectFrame(page);
  });
});
