// OIDC client of the BFF (openid-client v6): authorization code with PKCE, client secret
// via HTTP Basic, all token handling on the server (F01-AC1, F01-AC3, F01-AC13).
// The IdP is chosen only by configuration (F01-AC19): Zitadel or the test OIDC server.
import * as client from "openid-client";

import type { LoginState } from "./login-state";
import { DEMO_ROLES, roleFromClaims, type RoleKey } from "./roles";
import type { NewSession, Refreshed, TokenSet } from "./session-store";

export type OidcSettings = {
  issuer: string;
  clientId: string;
  clientSecret?: string;
  scopes: string;
  rolesClaim: string;
  appOrigin: string;
};

export function oidcSettings(env = process.env): OidcSettings {
  const required = (name: string) => {
    const value = env[name];
    if (!value) throw new Error(`${name} is not set`);
    return value;
  };
  return {
    issuer: required("OIDC_ISSUER"),
    clientId: required("OIDC_CLIENT_ID"),
    clientSecret: env.OIDC_CLIENT_SECRET || undefined,
    scopes: required("OIDC_SCOPES"),
    rolesClaim: env.OIDC_ROLES_CLAIM || "urn:zitadel:iam:org:project:roles",
    appOrigin: required("APP_ORIGIN"),
  };
}

let configuration: Promise<client.Configuration> | undefined;

/** Discovery once per server process. */
export function oidcConfig(settings = oidcSettings()): Promise<client.Configuration> {
  configuration ??= (async () => {
    const issuer = new URL(settings.issuer);
    // Plain http only for the local test OIDC server, never for a real IdP.
    const local =
      issuer.protocol === "http:" && ["localhost", "127.0.0.1"].includes(issuer.hostname);
    const auth = settings.clientSecret
      ? client.ClientSecretBasic(settings.clientSecret)
      : client.None();
    const config = await client.discovery(
      issuer,
      settings.clientId,
      undefined,
      auth,
      local ? { execute: [client.allowInsecureRequests] } : undefined,
    );
    return config;
  })().catch((error) => {
    configuration = undefined; // retry discovery on the next request
    throw error;
  });
  return configuration;
}

const callbackUrl = (settings: OidcSettings) => `${settings.appOrigin}/auth/callback`;

/** Login URL for the role plus the state that goes into the one-time cookie. */
export async function startLogin(
  config: client.Configuration,
  settings: OidcSettings,
  role: RoleKey,
): Promise<{ url: URL; state: LoginState }> {
  const state: LoginState = {
    state: client.randomState(),
    nonce: client.randomNonce(),
    verifier: client.randomPKCECodeVerifier(),
    role,
  };
  const url = client.buildAuthorizationUrl(config, {
    redirect_uri: callbackUrl(settings),
    scope: settings.scopes,
    code_challenge: await client.calculatePKCECodeChallenge(state.verifier),
    code_challenge_method: "S256",
    state: state.state,
    nonce: state.nonce,
    prompt: "login", // always ask for credentials, also after a role switch (F01-AC13)
    login_hint: DEMO_ROLES[role].username,
  });
  return { url, state };
}

export class NoKnownRole extends Error {}

/**
 * Redeems the code (checks state, nonce, PKCE, ID token) and returns the session to store.
 * Throws on any failed check; the caller shows the error page and creates no session.
 */
export async function finishLogin(
  config: client.Configuration,
  settings: OidcSettings,
  currentUrl: URL,
  state: LoginState,
): Promise<NewSession> {
  // The URL the IdP redirected to, rebuilt on our own origin (proxies may change the host).
  const url = new URL(`${callbackUrl(settings)}${currentUrl.search}`);
  const response = await client.authorizationCodeGrant(config, url, {
    pkceCodeVerifier: state.verifier,
    expectedState: state.state,
    expectedNonce: state.nonce,
    idTokenExpected: true,
  });
  const claims = response.claims();
  if (!claims) throw new Error("no ID token");
  const role = roleFromClaims(claims as Record<string, unknown>, settings.rolesClaim);
  if (!role) throw new NoKnownRole();
  return {
    sub: claims.sub,
    appRole: role,
    displayName: DEMO_ROLES[role].label,
    tokens: {
      access: response.access_token,
      refresh: response.refresh_token ?? null,
      id: response.id_token ?? null,
    },
    accessExpiresAt: expiresAt(response.expiresIn()),
  };
}

function expiresAt(seconds: number | undefined): Date {
  // Without expires_in, assume a short lifetime: the next request refreshes early.
  return new Date(Date.now() + (seconds ?? 300) * 1000);
}

export async function refreshTokens(
  config: client.Configuration,
  refreshToken: string,
): Promise<Refreshed> {
  const response = await client.refreshTokenGrant(config, refreshToken);
  return {
    tokens: {
      access: response.access_token,
      refresh: response.refresh_token,
      id: response.id_token,
    },
    accessExpiresAt: expiresAt(response.expiresIn()),
  };
}

/** Best effort: the session row is deleted anyway, a failed revocation must not block logout. */
export async function revokeTokens(config: client.Configuration, tokens: TokenSet): Promise<void> {
  const calls = [];
  if (tokens.refresh) {
    calls.push(
      client.tokenRevocation(config, tokens.refresh, { token_type_hint: "refresh_token" }),
    );
  }
  calls.push(client.tokenRevocation(config, tokens.access, { token_type_hint: "access_token" }));
  await Promise.allSettled(calls);
}

/** IdP logout without id_token_hint, so no token ever reaches the browser (Spike S2). */
export function endSessionUrl(config: client.Configuration, settings: OidcSettings): URL {
  return client.buildEndSessionUrl(config, {
    client_id: settings.clientId,
    post_logout_redirect_uri: `${settings.appOrigin}/`,
  });
}

const ROLE_SWITCH = /^\/auth\/login\?role=(wb1|wb2|pdl)$/;

/** `next` after logout: only the fixed role-switch targets, nothing else (no open redirect). */
export function safeNext(next: string | null): string | null {
  return next && ROLE_SWITCH.test(next) ? next : null;
}

/**
 * Where the browser goes after logout: the next login (role switch), else the IdP logout
 * page. If the IdP cannot be reached the session is already gone locally, so the start
 * page is a safe fallback (logout must never fail because of the IdP).
 */
export async function logoutTarget(
  next: string | null,
  appOrigin: string,
  idpLogout: () => Promise<URL>,
): Promise<URL> {
  const allowed = safeNext(next);
  if (allowed) return new URL(allowed, appOrigin);
  try {
    return await idpLogout();
  } catch {
    return new URL("/", appOrigin);
  }
}
