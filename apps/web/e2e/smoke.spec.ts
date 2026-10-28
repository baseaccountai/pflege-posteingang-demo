import { expect, test } from "@playwright/test";

test("start page shows sample-data banner and disclaimer footer", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.getByRole("status")).toHaveText("MUSTERDATEN · keine echten Personen");
  await expect(page.getByTestId("disclaimer")).toHaveText(
    "Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt",
  );
  // F10-AC15
  await expect(page.getByRole("contentinfo")).toContainText("jede Nacht um 3 Uhr");
});
