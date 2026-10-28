// F11-AC4: the main navigation sits at the bottom on the phone and at the side on wider
// screens; it shows the four areas and marks the current one.
import { expect, test } from "@playwright/test";

import { loginAs, uniqueUser } from "./support/auth";

test("the navigation is at the bottom on the phone and at the side on the desktop", async ({ page, isMobile }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto("/bewohner");
  const nav = page.getByRole("navigation", { name: "Hauptnavigation" });
  await expect(nav.getByRole("link")).toHaveText(["Start", "Posteingang", "Bewohner", "Fragen"]);
  await expect(nav.getByRole("link", { name: "Bewohner" })).toHaveAttribute("aria-current", "page");

  const box = (await nav.boundingBox())!;
  const viewport = page.viewportSize()!;
  if (isMobile) {
    expect(Math.round(box.y + box.height)).toBe(viewport.height); // stuck to the bottom
    expect(box.width).toBe(viewport.width);
  } else {
    expect(box.x).toBe(0); // left side bar
    expect(box.width).toBeLessThan(260);
  }

  await nav.getByRole("link", { name: "Fragen" }).click();
  await page.waitForURL("/fragen");
  await expect(nav.getByRole("link", { name: "Fragen" })).toHaveAttribute("aria-current", "page");
});

test("without a session there is no main navigation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Hauptnavigation" })).toHaveCount(0);
});
