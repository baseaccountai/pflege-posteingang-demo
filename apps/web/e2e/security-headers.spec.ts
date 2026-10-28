// F11-AC11: security headers on pages, a fresh nonce per response, a fixed CSP for the
// static offline page.
import { expect, test } from "@playwright/test";

test("pages carry the security headers and a nonce CSP without eval or inline scripts", async ({ request }) => {
  const first = await request.get("/");
  const second = await request.get("/");
  const headers = first.headers();
  expect(headers["strict-transport-security"]).toContain("max-age=");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["permissions-policy"]).toContain("camera=(self)");
  const csp = headers["content-security-policy"];
  expect(csp).toMatch(/script-src 'self' 'nonce-[^']+' 'strict-dynamic'/);
  expect(csp).not.toContain("unsafe-eval");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(second.headers()["content-security-policy"]).not.toBe(csp); // a new nonce each time
  // The nonce of the header is the one on the page's scripts.
  const nonce = /'nonce-([^']+)'/.exec(csp)![1];
  expect(await first.text()).toContain(`nonce="${nonce}"`);
});

test("the offline page has a fixed CSP without scripts", async ({ request }) => {
  const csp = (await request.get("/offline.html")).headers()["content-security-policy"];
  expect(csp).toContain("default-src 'none'");
  expect(csp).not.toMatch(/script-src/);
});
