import { execFileSync } from "node:child_process";

import { MOCK_OIDC_CONTAINER } from "./env";

// Playwright ends only the docker client; the test OIDC container is removed here.
export default function globalTeardown() {
  try {
    execFileSync("docker", ["rm", "-f", MOCK_OIDC_CONTAINER], { stdio: "ignore" });
  } catch {
    // already gone
  }
}
