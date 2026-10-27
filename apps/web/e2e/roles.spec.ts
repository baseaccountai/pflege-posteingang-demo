// F01-AC2, AC12, AC13 (role switch), AC14, AC20, AC21: start page, header, residents, no access.
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

import { admin, loginAs, sessionCookie, sessionRows, signInAtMockIdp, uniqueUser } from "./support/auth";
import { APP_ORIGIN, MOCK_OIDC_ISSUER, WB1_RESIDENT, WB2_RESIDENT } from "./support/env";

const NO_ACCESS = "Nicht gefunden oder kein Zugriff";

test("start page offers the three roles with their credentials (AC2)", async ({ page }) => {
  await page.goto("/");
  for (const [label, username, password] of [
    ["Pflegekraft WB1", "pflege-wb1", "Pflege-WB1-Demo!"],
    ["Pflegekraft WB2", "pflege-wb2", "Pflege-WB2-Demo!"],
    ["Pflegedienstleitung", "pdl", "Pflege-PDL-Demo1!"],
  ]) {
    const card = page.getByRole("group", { name: label });
    await expect(card).toContainText(username);
    await expect(card).toContainText(password);
    await expect(card.getByRole("button", { name: `Als ${label} anmelden` })).toBeVisible();
  }
  await expect(page.getByRole("banner")).toContainText("Nicht angemeldet");
});

test("header shows the role and logs out with a click (AC20, AC13)", async ({ page }) => {
  const user = uniqueUser();
  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  const header = page.getByRole("banner");
  await expect(header).toContainText("Pflegekraft WB1");

  const endSession = page.waitForRequest((r) => r.url().startsWith(`${MOCK_OIDC_ISSUER}/endsession`));
  await header.getByRole("button", { name: "Abmelden" }).click();
  await endSession;
  await expect.poll(() => sessionRows(user)).toHaveLength(0);
});

test("residents page shows only the own ward and is not cached (AC14)", async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  const response = await page.goto("/bewohner");
  expect(response?.headers()["cache-control"]).toContain("no-store");
  await expect(page.getByRole("link", { name: WB1_RESIDENT.name })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(WB2_RESIDENT.name);
});

test("PDL sees both wards", async ({ page }) => {
  await loginAs(page, "pdl", uniqueUser("pdl"), ["pdl"]);
  await page.goto("/bewohner");
  await expect(page.getByRole("link", { name: WB1_RESIDENT.name })).toBeVisible();
  await expect(page.getByRole("link", { name: WB2_RESIDENT.name })).toBeVisible();
});

test("role switch WB1 -> WB2 leaves no WB1 data anywhere (AC13)", async ({ page, request }) => {
  const wb1 = uniqueUser();
  const wb2 = uniqueUser("pflege-wb2");
  await loginAs(page, "wb1", wb1, ["nurse_wb1"]);
  await page.goto("/bewohner");
  await expect(page.getByRole("link", { name: WB1_RESIDENT.name })).toBeVisible();
  const oldCookie = (await sessionCookie(page))!;

  await page.goto("/");
  const authorize = page.waitForRequest((r) => r.url().startsWith(`${MOCK_OIDC_ISSUER}/authorize`));
  await page
    .getByRole("group", { name: "Pflegekraft WB2" })
    .getByRole("button", { name: "Als Pflegekraft WB2 anmelden" })
    .click();
  const params = new URL((await authorize).url()).searchParams;
  expect(params.get("login_hint")).toBe("pflege-wb2");
  expect(params.get("prompt")).toBe("login");
  // The WB1 session is gone on the server before the new login.
  expect(await sessionRows(wb1)).toHaveLength(0);

  await signInAtMockIdp(page, wb2, ["nurse_wb2"]);
  await page.waitForURL("/");
  await expect(page.getByRole("banner")).toContainText("Pflegekraft WB2");
  await page.goto("/bewohner");
  await expect(page.getByRole("link", { name: WB2_RESIDENT.name })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(WB1_RESIDENT.name);

  // Back button through the whole history: no page shows WB1 data again, including the
  // WB1 residents page from before the switch (which the loop must actually reach).
  let residentPagesSeen = 0;
  for (let i = 0; i < 10; i++) {
    if (!(await page.goBack())) break;
    await page.waitForLoadState();
    const url = new URL(page.url());
    if (url.origin !== APP_ORIGIN) continue;
    if (url.pathname === "/bewohner") residentPagesSeen++;
    await expect(page.locator("body")).not.toContainText(WB1_RESIDENT.name);
  }
  expect(residentPagesSeen).toBeGreaterThanOrEqual(1);

  // The old session id is worthless now.
  const replay = await request.get("/bewohner", {
    headers: { cookie: `${oldCookie.name}=${oldCookie.value}` },
  });
  expect(await replay.text()).not.toContain(WB1_RESIDENT.name);
});

test("a role switch in one tab clears WB1 data from the other tabs (AC13)", async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  const otherTab = await page.context().newPage();
  await otherTab.goto("/bewohner");
  await expect(otherTab.getByRole("link", { name: WB1_RESIDENT.name })).toBeVisible();

  await page.goto("/");
  const authorize = page.waitForRequest((r) => r.url().startsWith(`${MOCK_OIDC_ISSUER}/authorize`));
  await page
    .getByRole("group", { name: "Pflegekraft WB2" })
    .getByRole("button", { name: "Als Pflegekraft WB2 anmelden" })
    .click();
  await authorize; // the switching tab itself reaches the IdP

  await otherTab.waitForURL("/");
  await expect(otherTab.locator("body")).not.toContainText(WB1_RESIDENT.name);
});

test("foreign, unknown and malformed resident ids give the same no-access page (AC12)", async ({
  page,
}) => {
  await loginAs(page, "wb2", uniqueUser("pflege-wb2"), ["nurse_wb2"]);
  const texts: string[] = [];
  for (const id of [WB1_RESIDENT.id, randomUUID(), "kein-uuid"]) {
    await page.goto(`/bewohner/${id}`);
    await expect(page.getByRole("heading", { name: NO_ACCESS })).toBeVisible();
    await expect(page.locator("body")).not.toContainText(WB1_RESIDENT.name);
    texts.push(await page.getByRole("main").innerText());
  }
  expect(new Set(texts).size).toBe(1);

  await page.goto(`/bewohner/${WB2_RESIDENT.id}`);
  await expect(page.getByRole("heading", { name: WB2_RESIDENT.name })).toBeVisible();
});

test("ended session leads to the start page with a hint (AC21)", async ({ page }) => {
  const user = uniqueUser();
  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  await admin`update bff.sessions set revoked_at = now() where sub = ${user}`;
  await page.goto("/bewohner");
  await page.waitForURL("/?sitzung=abgelaufen");
  await expect(page.getByText("Sitzung abgelaufen – bitte Rolle wählen")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(WB1_RESIDENT.name);
});

test("session past its 8 h end leads to the start page with a hint (AC21)", async ({ page }) => {
  const user = uniqueUser();
  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  await admin`update bff.sessions set expires_at = now() - interval '1 second' where sub = ${user}`;
  // The browser still holds the cookie: it lives longer than the session.
  expect((await sessionCookie(page))!.expires * 1000).toBeGreaterThan(Date.now() + 8 * 3600_000);
  await page.goto("/bewohner");
  await page.waitForURL("/?sitzung=abgelaufen");
  await expect(page.getByText("Sitzung abgelaufen – bitte Rolle wählen")).toBeVisible();
});

test("a plain link to the login does not end an active session (no logout CSRF)", async ({
  page,
}) => {
  const user = uniqueUser();
  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  // What a foreign page can do: a top-level GET, with the Lax cookie attached.
  await page.goto("/auth/login?role=wb2");
  await page.waitForURL("/");
  expect(await sessionRows(user)).toHaveLength(1);
  await expect(page.getByRole("banner")).toContainText("Pflegekraft WB1");
});

test("residents page without a session goes to the start page", async ({ page }) => {
  await page.goto("/bewohner");
  await page.waitForURL("/");
  await expect(page.getByText("Sitzung abgelaufen")).toHaveCount(0);
});
