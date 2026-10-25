import { expect, test } from "@playwright/test";

test("start page shows sample-data banner and disclaimer footer", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.getByRole("status")).toHaveText("MUSTERDATEN · keine echten Personen");
  await expect(page.getByRole("contentinfo")).toHaveText(
    "Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt",
  );
});
