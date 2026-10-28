// F11-AC2, AC3 in a real browser: after a typical session the service worker cache holds
// nothing but build files, icons and the offline page; without network a page shows the
// offline page.
import { expect, test, type Page } from "@playwright/test";

import { loginAs, uniqueUser } from "./support/auth";
import { WB1_RESIDENT } from "./support/env";

const ALLOWED = [/^\/_next\/static\//, /^\/icons\//, /^\/offline\.html$/];

async function workerReady(page: Page) {
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
}

test("after a typical session the cache holds only the allowed files", async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await workerReady(page);
  await page.reload(); // now the worker sees every request of the page
  for (const path of ["/posteingang", "/bewohner", `/bewohner/${WB1_RESIDENT.id}`, "/fragen", "/muster"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
  }
  await page.getByRole("link", { name: "Start" }).first().click();
  await page.waitForLoadState("networkidle");

  const cached = await page.evaluate(async () => {
    const names = await caches.keys();
    const urls: string[] = [];
    for (const name of names) for (const request of await (await caches.open(name)).keys()) urls.push(request.url);
    return { names, urls };
  });
  expect(cached.names).toEqual(["pp-static-v1"]);
  const paths = cached.urls.map((url) => new URL(url).pathname);
  expect(paths).toContain("/offline.html");
  expect(paths.some((p) => p.startsWith("/_next/static/"))).toBe(true);
  for (const path of paths) expect(ALLOWED.some((rule) => rule.test(path)), path).toBe(true);
});

test("without network a page shows the offline page", async ({ page, context }) => {
  await page.goto("/");
  await workerReady(page);
  await context.setOffline(true);
  await page.goto("/bewohner").catch(() => {});
  await expect(page.getByRole("heading", { name: "Keine Verbindung – die Demo braucht Internet" })).toBeVisible();
  await expect(page.getByText("MUSTERDATEN · keine echten Personen")).toBeVisible();
  await context.setOffline(false);
});

test("the service worker itself is never cached by the browser", async ({ request }) => {
  const response = await request.get("/sw.js");
  expect(response.headers()["cache-control"]).toContain("no-cache");
  expect(response.headers()["service-worker-allowed"]).toBe("/");
});
