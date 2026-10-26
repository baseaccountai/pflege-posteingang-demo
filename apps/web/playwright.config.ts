import { defineConfig, devices } from "@playwright/test";

import {
  API_ENV,
  API_PORT,
  APP_ENV,
  APP_PORT,
  MOCK_OIDC_CONTAINER,
  MOCK_OIDC_IMAGE,
  MOCK_OIDC_ISSUER,
  MOCK_OIDC_PORT,
} from "./e2e/support/env";

// Needs the local Supabase stack (make db-start), Docker for the test OIDC server and uv for
// the API.
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/support/global-setup.ts",
  globalTeardown: "./e2e/support/global-teardown.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${APP_PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      // Test OIDC server with a login form (user name + claims), F01-AC19.
      // Fixed name: Playwright stops only the docker client, so a leftover container is removed
      // before the start (and with --rm when the client ends normally).
      command:
        `docker rm -f ${MOCK_OIDC_CONTAINER} >/dev/null 2>&1; ` +
        `docker run --rm --name ${MOCK_OIDC_CONTAINER} -p ${MOCK_OIDC_PORT}:8080 ` +
        `-e JSON_CONFIG ${MOCK_OIDC_IMAGE}`,
      env: { JSON_CONFIG: JSON.stringify({ interactiveLogin: true }) },
      url: `${MOCK_OIDC_ISSUER}/.well-known/openid-configuration`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      // FastAPI with the same test IdP (needs uv); started after the IdP for JWKS discovery.
      command: `uv run --directory ../api uvicorn app.main:app --port ${API_PORT}`,
      env: API_ENV,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      // Build first (`pnpm e2e` does it); start next directly so Playwright can stop it cleanly.
      command: `node_modules/.bin/next start --port ${APP_PORT}`,
      env: APP_ENV,
      url: `http://localhost:${APP_PORT}`,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
