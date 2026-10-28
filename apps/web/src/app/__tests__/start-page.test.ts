// @vitest-environment node
// F09-AC7: the start page renders without the API and without the database - checked on
// the imports: neither the page nor anything it pulls in may reach the API client, the
// session store or the record queries.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "../..");
const FORBIDDEN = ["@/lib/api", "@/lib/as-caller", "@/lib/residents", "@/lib/auth/current", "@/lib/auth/session"];

function resolve(spec: string): string | null {
  if (!spec.startsWith("@/")) return null;
  const base = path.join(SRC, spec.slice(2));
  return [".tsx", ".ts", "/index.ts"].map((ext) => base + ext).find((file) => existsSync(file)) ?? null;
}

/** All "@/…" modules reachable from `file` through imports. */
function imports(file: string, seen = new Map<string, string>()): Map<string, string> {
  const source = readFileSync(file, "utf8");
  for (const [, spec] of source.matchAll(/from\s+"([^"]+)"/g)) {
    if (!spec.startsWith("@/") || seen.has(spec)) continue;
    seen.set(spec, file);
    const target = resolve(spec);
    if (target) imports(target, seen);
  }
  return seen;
}

describe("start page", () => {
  it("pulls in no API, session or database code", () => {
    const reached = imports(path.join(SRC, "app/page.tsx"));
    expect(reached.has("@/components/requirements-map")).toBe(true); // the walk works
    for (const forbidden of FORBIDDEN) {
      expect(reached.has(forbidden), `${forbidden} via ${reached.get(forbidden)}`).toBe(false);
    }
  });
});
