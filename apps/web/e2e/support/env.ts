// Fixed values for the end-to-end tests: test OIDC server (mock-oauth2-server) and the
// local Supabase database. Local-only secrets, never used outside tests.
export const APP_PORT = 3100;
export const APP_ORIGIN = `http://localhost:${APP_PORT}`;
export const MOCK_OIDC_PORT = 18080;
export const MOCK_OIDC_ISSUER = `http://localhost:${MOCK_OIDC_PORT}/default`;
export const MOCK_OIDC_IMAGE = "ghcr.io/navikt/mock-oauth2-server:2.1.10";
export const MOCK_OIDC_CONTAINER = "pflege-e2e-oidc";

export const ADMIN_DSN =
  process.env.TEST_ADMIN_DATABASE_URL ?? "postgresql://postgres:postgres@127.0.0.1:56322/postgres";
export const BFF_PASSWORD = "bff_session_local_test";
export const BFF_DSN = `postgresql://bff_session:${BFF_PASSWORD}@127.0.0.1:56322/postgres`;
export const SESSION_ENC_KEY = Buffer.alloc(32, 7).toString("base64");

/** Environment of `next start` during the tests (F01-AC19: IdP only via configuration). */
export const APP_ENV = {
  APP_ORIGIN,
  OIDC_ISSUER: MOCK_OIDC_ISSUER,
  OIDC_CLIENT_ID: "pflege-e2e",
  OIDC_CLIENT_SECRET: "e2e-client-secret",
  OIDC_SCOPES: "openid profile offline_access",
  OIDC_ROLES_CLAIM: "roles",
  SESSION_ENC_KEY,
  BFF_DATABASE_URL: BFF_DSN,
};
