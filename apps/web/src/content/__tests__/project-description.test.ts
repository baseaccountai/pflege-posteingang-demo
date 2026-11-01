// @vitest-environment node
// Phase 9 (design 8.3): docs/projektbeschreibung.md is the only source of the project
// description. The app's copy (src/content/project-description.ts, written by
// `make project-description`) must be the same,
// every picture must be copied too, and every repository link must lead to a real file.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { PROJECT_DESCRIPTION } from "@/content/project-description";

const REPO_ROOT = path.resolve(__dirname, "../../../../..");
const SOURCE = path.join(REPO_ROOT, "docs/projektbeschreibung.md");
const PUBLIC_DIR = path.resolve(__dirname, "../../../public/projekt");

const SECTIONS = [
  "Was die Anwendung macht",
  "Bezug zur Stelle",
  "Technologie",
  "Architektur",
  "Sicherheit und Datenschutz",
  "Vorgehen",
  "Ergebnisse und Ausblick",
  "Betrieb",
];

const text = () => readFileSync(SOURCE, "utf8");
/** Targets of Markdown links and images: [..](target) and ![..](target). */
const targets = (markdown: string) => [...markdown.matchAll(/\]\(([^)\s]+)\)/g)].map((m) => m[1]);

describe("project description", () => {
  it("has the sections of design 8.3, in that order", () => {
    const headings = [...text().matchAll(/^## (.+)$/gm)].map((m) => m[1]);
    expect(headings).toEqual(SECTIONS);
  });

  it("is copied unchanged into the app (make project-description)", () => {
    expect(PROJECT_DESCRIPTION).toBe(text());
  });

  it("has every picture copied unchanged into public/projekt/", () => {
    const pictures = targets(text()).filter((t) => t.startsWith("assets/projekt/"));
    expect(pictures.length).toBeGreaterThan(0);
    for (const picture of pictures) {
      const copy = path.join(PUBLIC_DIR, path.basename(picture));
      expect(existsSync(copy), picture).toBe(true);
      expect(readFileSync(copy).equals(readFileSync(path.join(REPO_ROOT, "docs", picture))), picture).toBe(true);
    }
  });

  it("links only to files and folders that exist in the repository", () => {
    for (const target of targets(text())) {
      if (/^[a-z]+:/.test(target) || target.startsWith("#")) continue;
      const file = path.resolve(REPO_ROOT, "docs", decodeURI(target.split("#")[0]));
      expect(existsSync(file), target).toBe(true);
    }
  });

  it("names the measured injection report, not planned numbers", () => {
    expect(text()).toContain("security/reports/2026-10-31-injection.md");
    expect(text()).toContain("89,6 %");
  });

  it("carries the fixed texts: sample data only, no product of the university", () => {
    expect(text()).toContain("erfundene Musterdaten");
    expect(text()).toContain("kein Produkt der Hochschule Anhalt");
  });
});
