// @vitest-environment node
// F11-AC11: the Content-Security-Policy of the app pages.
import { describe, expect, it } from "vitest";

import { contentSecurityPolicy } from "@/lib/security/csp";

const directives = (csp: string) =>
  Object.fromEntries(csp.split(";").map((d) => d.trim().split(/\s+/)).map(([name, ...values]) => [name, values]));

describe("contentSecurityPolicy", () => {
  const csp = directives(contentSecurityPolicy("abc123", "https://idp.example/realm"));

  it("allows scripts only from here with the nonce, no eval, no inline", () => {
    expect(csp["script-src"]).toEqual(["'self'", "'nonce-abc123'", "'strict-dynamic'"]);
    expect(Object.values(csp).flat()).not.toContain("'unsafe-eval'");
    expect(csp["script-src"]).not.toContain("'unsafe-inline'");
  });

  it("keeps everything else on this origin and cannot be framed", () => {
    expect(csp["default-src"]).toEqual(["'self'"]);
    expect(csp["connect-src"]).toEqual(["'self'"]);
    expect(csp["object-src"]).toEqual(["'none'"]);
    expect(csp["base-uri"]).toEqual(["'self'"]);
    expect(csp["frame-ancestors"]).toEqual(["'none'"]);
    expect(csp["img-src"]).toEqual(["'self'", "blob:", "data:"]);
    expect(csp["style-src"]).toEqual(["'self'", "'nonce-abc123'"]);
  });

  it("lets forms go to the identity provider (login and logout redirect there)", () => {
    expect(csp["form-action"]).toEqual(["'self'", "https://idp.example"]);
  });

  it("allows eval only in development (React's dev tools need it)", () => {
    const dev = directives(contentSecurityPolicy("n", "https://idp.example", true));
    expect(dev["script-src"]).toContain("'unsafe-eval'");
  });

  it("works without a configured identity provider", () => {
    expect(directives(contentSecurityPolicy("n", undefined))["form-action"]).toEqual(["'self'"]);
  });
});
