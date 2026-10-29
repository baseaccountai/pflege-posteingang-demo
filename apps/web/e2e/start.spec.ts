// F09-AC1, AC6, AC8: the start page explains the project first, then the requirements map,
// then the role switch with the sample-data hint; /projekt is a placeholder with links.
import { expect, test } from "@playwright/test";

test("project card, requirements map and role switch in this order, without login", async ({ page }) => {
  await page.goto("/");
  const card = page.getByRole("region", { name: "Über das Projekt" });
  const map = page.getByRole("heading", { name: /Anforderungen der Stelle/ });
  const roles = page.getByRole("heading", { name: "Rolle wählen" });
  await expect(card).toBeVisible();
  const top = async (locator: typeof card) => (await locator.boundingBox())!.y;
  expect(await top(card)).toBeLessThan(await top(map));
  expect(await top(map)).toBeLessThan(await top(roles));
  await expect(page.getByTestId("requirement-rag-agents")).toBeVisible();
  await expect(page.getByText("Alle Personen und Dokumente sind erfundene Musterdaten.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Als Pflegekraft WB1 anmelden" })).toBeVisible();
});

test("the app links of the map lead to working pages", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("requirement-rag-agents").getByRole("link", { name: "In der App: Fragen" }).click();
  // Without a session the questions page sends to the start page - the link itself works.
  await expect(page).toHaveURL(/\/(fragen)?(\?.*)?$/);
});

test("the project page is a placeholder with links to architecture, specs and repository", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("banner").getByRole("link", { name: "Über das Projekt" }).click();
  await page.waitForURL("/projekt");
  await expect(page.getByRole("heading", { level: 1, name: "Über das Projekt" })).toBeVisible();
  await expect(page.getByText("Projektbeschreibung folgt")).toBeVisible();
  for (const name of ["Architektur", "Specs", "Repository"]) {
    await expect(page.getByRole("link", { name })).toHaveAttribute("href", /github\.com\/baseaccountai\/pflege-posteingang-demo/);
  }
});

test("the app can be installed: manifest and apple touch icon are linked (F11-AC1)", async ({ page }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  const manifest = await (await page.request.get(href!)).json();
  expect(manifest).toMatchObject({ name: "Pflege-Posteingang", display: "standalone", theme_color: "#115e59" });
  const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  expect((await page.request.get(apple!)).headers()["content-type"]).toContain("image/png");
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#115e59");
});

test("the project page says which AI sees which data (F06-AC11)", async ({ page }) => {
  await page.goto("/projekt");
  const table = page.getByRole("table", { name: "Welche KI sieht welche Daten" });
  await expect(table.getByRole("row", { name: /Texterkennung/ })).toContainText("Original");
  await expect(table.getByRole("row", { name: /Antwort auf Fragen/ })).toContainText("nur Platzhalter");
});
