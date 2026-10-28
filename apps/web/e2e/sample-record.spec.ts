// F10-AC14: /muster shows a static sample record without login; the original opens as a
// static file. (That the page needs no API is shown in Vitest: sample-record-section.test.)
import { expect, test } from "@playwright/test";

test("the sample record is public and shows medication, origin and the document", async ({ page }) => {
  await page.goto("/muster");
  await expect(page.getByRole("heading", { level: 1, name: "Fr. Beispiel" })).toBeVisible();
  await expect(page.getByText("MUSTERDATEN · keine echten Personen")).toBeVisible();
  await expect(page.getByText(/Unabhängige Bewerbungsdemo, inspiriert von KLARA/)).toBeVisible();
  await expect(page.getByText(/Statische Musterakte/)).toBeVisible();

  const medication = page.getByRole("region", { name: "Medikation" });
  await expect(medication.getByText("Metamizol 500 mg")).toBeVisible();
  await expect(medication.getByTestId("provenance").first()).toContainText("freigegeben von Pflegekraft WB1");
  await expect(page.getByRole("button", { name: /erledigt/i })).toHaveCount(0);

  const documentLink = page.getByRole("region", { name: "Dokumente" }).getByRole("link").first();
  const href = await documentLink.getAttribute("href");
  expect(href).toMatch(/^\/muster\/5eed[0-9a-f-]+\.pdf$/);
  const file = await page.request.get(href!);
  expect(file.status()).toBe(200);
  expect(file.headers()["content-type"]).toContain("application/pdf");
});
