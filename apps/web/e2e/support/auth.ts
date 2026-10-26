import { createHash, randomUUID } from "node:crypto";
import { expect, type Page } from "@playwright/test";
import postgres from "postgres";

import { openTokens, parseEncKey, type TokenSet } from "../../src/lib/auth/session-store";
import { ADMIN_DSN, SESSION_ENC_KEY } from "./env";

// Closes idle connections by itself, so no worker hook has to end it.
export const admin = postgres(ADMIN_DSN, { max: 2, idle_timeout: 1, onnotice: () => {} });

/** A user name per test, so parallel tests (and projects) never share session rows. */
export function uniqueUser(prefix = "pflege-wb1") {
  return `${prefix}-${randomUUID().slice(0, 8)}`;
}

/**
 * Fills the login form of the test OIDC server. Its `sub` is the user name; the roles
 * claim is set like Zitadel's project roles, but in the list form (F01-AC19).
 */
export async function signInAtMockIdp(page: Page, username: string, roles: string[]) {
  await page.locator('input[name="username"]').fill(username);
  await page.locator('textarea[name="claims"]').fill(JSON.stringify({ roles }));
  await page.getByRole("button", { name: "Sign-in" }).click();
}

export async function loginAs(page: Page, role: string, username: string, idpRoles: string[]) {
  await page.goto(`/auth/login?role=${role}`);
  await signInAtMockIdp(page, username, idpRoles);
  await page.waitForURL("/");
}

export type SessionRow = {
  id_hash: Buffer;
  app_role: string;
  display_name: string;
  tokens_enc: Buffer;
};

export async function sessionRows(sub: string): Promise<SessionRow[]> {
  return admin<SessionRow[]>`
    select id_hash, app_role, display_name, tokens_enc from bff.sessions where sub = ${sub}`;
}

/** The real tokens of a session, decrypted with the test key (to search for them). */
export function tokensOf(row: SessionRow): TokenSet {
  const key = parseEncKey(SESSION_ENC_KEY);
  return openTokens(Buffer.from(row.tokens_enc), key, Buffer.from(row.id_hash));
}

export const sha256 = (value: string) => createHash("sha256").update(value).digest();

export async function sessionCookie(page: Page) {
  return (await page.context().cookies()).find((c) => c.name === "__Host-pp_sid");
}

/** Submits a real form POST from the page (the browser sets Origin itself). */
export async function postForm(page: Page, action: string) {
  await page.evaluate((url) => {
    const form = document.createElement("form");
    form.method = "post";
    form.action = url;
    document.body.append(form);
    form.submit();
  }, action);
}

export async function expectErrorPage(page: Page) {
  await expect(page.getByRole("heading", { name: "Anmeldung fehlgeschlagen" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Zur Startseite" })).toHaveAttribute("href", "/");
}
