// @vitest-environment node
// F09-AC3 to AC5: one data file for the requirements map; every app link is a real route,
// every repo path exists, unfinished features say "Stufe 2" instead of linking nowhere.
import { existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { REQUIREMENTS, SECURITY_REPORT, repoHref } from "@/content/requirements-map";

const APP_DIR = path.resolve(__dirname, "../../app");
const REPO_ROOT = path.resolve(__dirname, "../../../../..");

/** Routes of the app router: every folder with a page.tsx ("[id]" matches any segment). */
function routes(dir = APP_DIR, prefix = ""): string[] {
  const found = existsSync(path.join(dir, "page.tsx")) ? [prefix || "/"] : [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory() && !name.startsWith("__") && name !== "api") {
      found.push(...routes(full, `${prefix}/${name}`));
    }
  }
  return found;
}

function isRoute(href: string): boolean {
  const wanted = href.split("?")[0].split("/").filter(Boolean);
  return routes().some((route) => {
    const parts = route.split("/").filter(Boolean);
    return parts.length === wanted.length && parts.every((p, i) => p.startsWith("[") || p === wanted[i]);
  });
}

describe("requirements map data", () => {
  it("lists the seven requirements of the job ad, four required and three desirable", () => {
    expect(REQUIREMENTS).toHaveLength(7);
    expect(REQUIREMENTS.filter((r) => r.level === "gefordert")).toHaveLength(4);
    expect(REQUIREMENTS.filter((r) => r.level === "wuenschenswert")).toHaveLength(3);
    expect(REQUIREMENTS.map((r) => r.text)).toContain("Anbindung von LLMs über APIs");
    expect(new Set(REQUIREMENTS.map((r) => r.id)).size).toBe(7);
  });

  it("describes how each requirement is met", () => {
    for (const entry of REQUIREMENTS) expect(entry.how.length, entry.id).toBeGreaterThan(20);
  });

  it("links only to routes that exist", () => {
    expect(routes()).toContain("/fragen"); // the route reader itself works
    for (const entry of REQUIREMENTS) {
      if (entry.appHref) expect(isRoute(entry.appHref), `${entry.id}: ${entry.appHref}`).toBe(true);
    }
  });

  it("names a security report only if the file is in the repository (F13-AC7)", () => {
    if (SECURITY_REPORT !== null) {
      expect(SECURITY_REPORT).toMatch(/^docs\/security\/reports\/\d{4}-\d{2}-\d{2}-injection\.md$/);
      expect(existsSync(path.join(REPO_ROOT, SECURITY_REPORT))).toBe(true);
    }
    expect(REQUIREMENTS.find((r) => r.id === "llm-security")?.repoPaths).toContain("apps/api/tests/security/");
  });

  it("links only to repo paths that exist", () => {
    for (const entry of REQUIREMENTS) {
      expect(entry.repoPaths.length, entry.id).toBeGreaterThan(0);
      for (const repoPath of entry.repoPaths) {
        expect(existsSync(path.join(REPO_ROOT, repoPath)), `${entry.id}: ${repoPath}`).toBe(true);
      }
    }
  });

  it("has no app link for what is still in Stufe 2", () => {
    const later = REQUIREMENTS.filter((r) => r.status === "stufe2");
    expect(later.map((r) => r.id)).toEqual([]); // local operation (F12) is done, too
    for (const entry of later) expect(entry.appHref).toBeUndefined();
  });

  it("builds repo links from the configured repository", () => {
    expect(repoHref("docs/architecture/", "https://github.com/x/y")).toBe("https://github.com/x/y/tree/main/docs/architecture/");
    expect(repoHref("infra/docker-compose.yml", "https://github.com/x/y")).toBe(
      "https://github.com/x/y/blob/main/infra/docker-compose.yml",
    );
    expect(repoHref("docs/")).toMatch(/^https:\/\/github\.com\/baseaccountai\/pflege-posteingang-demo\/tree\/main\/docs\/$/);
  });
});

describe("stage 2 entries", () => {
  it("shows the prompt-injection protection as live, with the inbox to try it (F07)", () => {
    const entry = REQUIREMENTS.find((r) => r.id === "llm-security")!;
    expect(entry.status).toBe("live");
    expect(entry.appHref).toBe("/posteingang");
    expect(entry.repoPaths).toContain("apps/api/app/security/");
    expect(entry.how).toMatch(/fünf Schichten/);
  });
});
