// @vitest-environment node
// F01-AC1 (login parameters), F01-AC13 (logout URL without tokens, fixed list for `next`).
import { Configuration } from "openid-client";
import { describe, expect, it } from "vitest";

import { endSessionUrl, safeNext, startLogin, type OidcSettings } from "../oidc";

const SETTINGS: OidcSettings = {
  issuer: "https://idp.example",
  clientId: "client-1",
  clientSecret: "secret",
  scopes: "openid profile offline_access",
  rolesClaim: "roles",
  appOrigin: "https://pflege.example",
};

const CONFIG = new Configuration(
  {
    issuer: "https://idp.example",
    authorization_endpoint: "https://idp.example/authorize",
    end_session_endpoint: "https://idp.example/end_session",
  },
  "client-1",
  "secret",
);

describe("startLogin", () => {
  it("builds a code + PKCE S256 login with state, nonce, prompt=login and login_hint", async () => {
    const { url, state } = await startLogin(CONFIG, SETTINGS, "wb2");
    const params = url.searchParams;
    expect(url.origin + url.pathname).toBe("https://idp.example/authorize");
    expect(params.get("response_type")).toBe("code");
    expect(params.get("client_id")).toBe("client-1");
    expect(params.get("redirect_uri")).toBe("https://pflege.example/auth/callback");
    expect(params.get("scope")).toBe("openid profile offline_access");
    expect(params.get("code_challenge_method")).toBe("S256");
    expect(params.get("code_challenge")).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(params.get("code_challenge")).not.toBe(state.verifier);
    expect(params.get("state")).toBe(state.state);
    expect(params.get("nonce")).toBe(state.nonce);
    expect(params.get("prompt")).toBe("login");
    expect(params.get("login_hint")).toBe("pflege-wb2");
    expect(state.role).toBe("wb2");
  });

  it("uses fresh random values per login", async () => {
    const a = (await startLogin(CONFIG, SETTINGS, "wb1")).state;
    const b = (await startLogin(CONFIG, SETTINGS, "wb1")).state;
    expect([a.state, a.nonce, a.verifier]).not.toContain(b.state);
    expect(a.verifier).not.toBe(b.verifier);
  });
});

describe("endSessionUrl", () => {
  it("carries client_id and post_logout_redirect_uri, but no token", () => {
    const url = endSessionUrl(CONFIG, SETTINGS);
    expect(url.origin + url.pathname).toBe("https://idp.example/end_session");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      client_id: "client-1",
      post_logout_redirect_uri: "https://pflege.example/",
    });
  });
});

describe("safeNext", () => {
  it.each(["wb1", "wb2", "pdl"])("allows the role switch to %s", (role) => {
    expect(safeNext(`/auth/login?role=${role}`)).toBe(`/auth/login?role=${role}`);
  });

  it.each([
    null,
    "",
    "/",
    "https://evil.example/auth/login?role=wb1",
    "//evil.example/auth/login?role=wb1",
    "/auth/login?role=admin",
    "/auth/login?role=wb1&next=x",
  ])("ignores %s", (next) => {
    expect(safeNext(next)).toBeNull();
  });
});
