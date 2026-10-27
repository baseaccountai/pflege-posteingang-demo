// F01-AC1, AC3, AC4, AC5, AC13 (logout), AC15, AC19: BFF login against the test OIDC server.
import { expect, test, type Request } from "@playwright/test";

import {
  expectErrorPage,
  loginAs,
  postForm,
  sessionCookie,
  sessionRows,
  sha256,
  signInAtMockIdp,
  tokensOf,
  uniqueUser,
} from "./support/auth";
import { APP_ORIGIN, MOCK_OIDC_ISSUER } from "./support/env";

test("login as WB1 starts code + PKCE with prompt=login and login_hint (AC1)", async ({ page }) => {
  const authorize = page.waitForRequest((r) => r.url().startsWith(`${MOCK_OIDC_ISSUER}/authorize`));
  await page.goto("/auth/login?role=wb1");
  const params = new URL((await authorize).url()).searchParams;
  expect(params.get("response_type")).toBe("code");
  expect(params.get("code_challenge_method")).toBe("S256");
  expect(params.get("prompt")).toBe("login");
  expect(params.get("login_hint")).toBe("pflege-wb1");
  expect(params.get("redirect_uri")).toBe(`${APP_ORIGIN}/auth/callback`);
  for (const name of ["state", "nonce", "code_challenge"]) expect(params.get(name)).toBeTruthy();
});

test("unknown role does not start a login", async ({ page }) => {
  await page.goto("/auth/login?role=admin");
  await expect(page).toHaveURL("/");
});

test("callback stores the session server-side, sets only __Host-pp_sid (AC3)", async ({ page }) => {
  const user = uniqueUser();
  await loginAs(page, "wb1", user, ["nurse_wb1"]);

  const cookie = await sessionCookie(page);
  expect(cookie).toMatchObject({ httpOnly: true, secure: true, sameSite: "Lax", path: "/" });
  expect(cookie?.value).toMatch(/^[A-Za-z0-9_-]{43}$/);
  const names = (await page.context().cookies(APP_ORIGIN)).map((c) => c.name);
  expect(names).toEqual(["__Host-pp_sid"]); // login state cookie is gone

  const [row, ...more] = await sessionRows(user);
  expect(more).toHaveLength(0);
  expect(row.id_hash).toEqual(sha256(cookie!.value));
  expect(row.app_role).toBe("wb1");
  expect(row.display_name).toBe("Pflegekraft WB1");
});

test("role comes from the ID token, not from the button (AC19)", async ({ page }) => {
  const user = uniqueUser("pdl");
  await page.goto("/auth/login?role=wb1");
  await signInAtMockIdp(page, user, ["pdl"]);
  await page.waitForURL("/");
  expect((await sessionRows(user))[0].app_role).toBe("pdl");
});

test("account without a known role gets the error page, no session", async ({ page }) => {
  const user = uniqueUser("nobody");
  await page.goto("/auth/login?role=wb1");
  await signInAtMockIdp(page, user, ["admin"]);
  await expectErrorPage(page);
  expect(await sessionRows(user)).toHaveLength(0);
  expect(await sessionCookie(page)).toBeUndefined();
});

test("no token reaches the browser, also not on logout (AC4, AC13)", async ({ page }) => {
  const user = uniqueUser();
  // Every app response the browser received completely (aborted prefetches never reach
  // the page, and waiting for their body would hang). Bodies are read as they arrive.
  const responseParts: Promise<string>[] = [];
  const collect = (request: Request) => {
    if (!request.url().startsWith(APP_ORIGIN)) return;
    responseParts.push(
      (async () => {
        const r = await request.response();
        if (!r) return "";
        const headers = JSON.stringify(await r.allHeaders());
        const body = r.status() >= 300 && r.status() < 400 ? "" : await r.text().catch(() => "");
        return `${r.url()} ${headers} ${body}`;
      })(),
    );
  };
  page.on("requestfinished", collect);
  // Every request URL, including each hop of a redirect chain (e.g. the IdP logout).
  const requestUrls: string[] = [];
  page.on("request", (r) => requestUrls.push(r.url()));

  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  const tokens = tokensOf((await sessionRows(user))[0]);
  const secrets = [tokens.access, tokens.refresh, tokens.id].filter((t): t is string => !!t);
  expect(secrets.length).toBe(3);

  const browserSide = [
    await page.content(),
    await page.evaluate(() => document.cookie),
    await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage })),
    JSON.stringify(await page.context().cookies()),
  ];

  const isIdpLogout = (url: string) => url.startsWith(`${MOCK_OIDC_ISSUER}/endsession`);
  const idpLogout = page.waitForRequest((r) => isIdpLogout(r.url()));
  await postForm(page, "/auth/logout");
  await idpLogout;
  await page.waitForLoadState();

  page.off("requestfinished", collect); // later prefetches would outlive the page
  const received = await Promise.all(responseParts);
  expect(received.length).toBeGreaterThan(3); // login, callback, start page, logout at least
  const everything = [...browserSide, ...received, ...requestUrls].join("\n");
  for (const secret of secrets) expect(everything).not.toContain(secret);
  // The logout goes to the IdP with client_id only (no id_token_hint).
  expect(requestUrls.some((u) => u.includes("id_token_hint"))).toBe(false);
});

test("logout revokes, deletes the row and the cookie, then goes to IdP logout (AC13)", async ({
  page,
}) => {
  const user = uniqueUser();
  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  const endSession = page.waitForRequest((r) =>
    r.url().startsWith(`${MOCK_OIDC_ISSUER}/endsession`),
  );
  await postForm(page, "/auth/logout");
  // Exactly these two parameters: no id_token_hint or other token in the URL.
  expect(Object.fromEntries(new URL((await endSession).url()).searchParams)).toEqual({
    client_id: "pflege-e2e",
    post_logout_redirect_uri: `${APP_ORIGIN}/`,
  });
  await expect.poll(() => sessionRows(user)).toHaveLength(0);
  await expect.poll(() => sessionCookie(page)).toBeUndefined();
});

test("manipulated state creates no session (AC5)", async ({ page }) => {
  const user = uniqueUser();
  // Catch the IdP's redirect to our callback without following it (the login state cookie
  // stays), then send the callback with a forged state.
  let callbackUrl: string | undefined;
  await page.route(`${MOCK_OIDC_ISSUER}/authorize**`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch({ maxRedirects: 0 });
    callbackUrl = response.headers()["location"];
    await route.fulfill({ status: 200, contentType: "text/plain", body: "angehalten" });
  });
  await page.goto("/auth/login?role=wb1");
  await signInAtMockIdp(page, user, ["nurse_wb1"]);
  await expect.poll(() => callbackUrl).toBeTruthy();
  const forged = new URL(callbackUrl!);
  expect(forged.pathname).toBe("/auth/callback");
  expect(forged.searchParams.get("code")).toBeTruthy();
  forged.searchParams.set("state", "forged-state");
  await page.goto(forged.toString());
  await expectErrorPage(page);
  expect(await sessionRows(user)).toHaveLength(0);
  expect(await sessionCookie(page)).toBeUndefined();
});

test("second use of the same callback creates no session (AC5)", async ({ page }) => {
  const user = uniqueUser();
  const callback = page.waitForRequest((r) => r.url().startsWith(`${APP_ORIGIN}/auth/callback`));
  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  const callbackUrl = (await callback).url();
  const first = await sessionCookie(page);
  // The login state is used up: without it the second callback cannot be redeemed.
  const names = (await page.context().cookies(APP_ORIGIN)).map((c) => c.name);
  expect(names).not.toContain("__Host-pp_oidc");

  await page.goto(callbackUrl);
  await expectErrorPage(page);
  expect(await sessionRows(user)).toHaveLength(1);
  expect((await sessionCookie(page))?.value).toBe(first?.value);
});

test("replaying the callback together with the captured login cookie fails (AC5)", async ({
  page,
}) => {
  const user = uniqueUser();
  let callbackUrl: string | undefined;
  await page.route(`${MOCK_OIDC_ISSUER}/authorize**`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch({ maxRedirects: 0 });
    callbackUrl = response.headers()["location"];
    await route.fulfill({ status: 200, contentType: "text/plain", body: "angehalten" });
  });
  await page.goto("/auth/login?role=wb1");
  await signInAtMockIdp(page, user, ["nurse_wb1"]);
  await expect.poll(() => callbackUrl).toBeTruthy();
  // What an attacker would have to steal: the callback URL and the HttpOnly login cookie.
  const loginCookie = (await page.context().cookies()).find((c) => c.name === "__Host-pp_oidc")!;
  expect(loginCookie).toBeTruthy();

  await page.goto(callbackUrl!);
  await page.waitForURL("/");
  expect(await sessionRows(user)).toHaveLength(1);

  await page.context().addCookies([loginCookie]);
  await page.goto(callbackUrl!);
  await expectErrorPage(page);
  // The test IdP accepts the code twice; only the server-side one-time state stops it.
  expect(await sessionRows(user)).toHaveLength(1);
});

test("callback without a login in progress shows the error page (AC5)", async ({ page }) => {
  await page.goto("/auth/callback?code=abc&state=xyz");
  await expectErrorPage(page);
  expect(await sessionCookie(page)).toBeUndefined();
});

test("POST without or with a foreign Origin is rejected with 403 (AC15)", async ({ page }) => {
  const user = uniqueUser();
  await loginAs(page, "wb1", user, ["nurse_wb1"]);
  const cookie = (await sessionCookie(page))!;
  const headers = { cookie: `${cookie.name}=${cookie.value}` };

  const withoutOrigin = await page.request.post("/auth/logout", { headers, maxRedirects: 0 });
  expect(withoutOrigin.status()).toBe(403);
  const foreign = await page.request.post("/auth/logout", {
    headers: { ...headers, origin: "https://evil.example" },
    maxRedirects: 0,
  });
  expect(foreign.status()).toBe(403);
  expect(await sessionRows(user)).toHaveLength(1); // session untouched
});

test("logout has no GET variant", async ({ page }) => {
  const response = await page.request.get("/auth/logout", { maxRedirects: 0 });
  expect(response.status()).toBe(405);
});
