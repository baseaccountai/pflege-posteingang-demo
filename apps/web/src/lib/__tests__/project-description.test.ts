// Phase 9: the project description is written for GitHub (docs/projektbeschreibung.md,
// links relative to docs/). In the app the same text links to the repository on GitHub and
// shows its pictures from public/projekt/.
import { describe, expect, it } from "vitest";

import { repoHref } from "@/content/requirements-map";
import { descriptionHref, descriptionImage } from "@/lib/project-description";

describe("descriptionHref", () => {
  it("turns a link relative to docs/ into a repository link", () => {
    expect(descriptionHref("architecture/architecture.md")).toBe(repoHref("docs/architecture/architecture.md"));
    expect(descriptionHref("specs/")).toBe(repoHref("docs/specs/"));
  });

  it("resolves links that leave docs/", () => {
    expect(descriptionHref("../apps/api/app/agent/")).toBe(repoHref("apps/api/app/agent/"));
    expect(descriptionHref("../README.md")).toBe(repoHref("README.md"));
  });

  it("keeps the anchor of a repository link", () => {
    expect(descriptionHref("security/threat-model.md#schutzgüter")).toBe(
      `${repoHref("docs/security/threat-model.md")}#schutzgüter`,
    );
  });

  it("leaves web addresses, app paths and anchors alone", () => {
    expect(descriptionHref("https://pflege-posteingang-demo.vercel.app")).toBe("https://pflege-posteingang-demo.vercel.app");
    expect(descriptionHref("mailto:x@example.org")).toBe("mailto:x@example.org");
    expect(descriptionHref("#betrieb")).toBe("#betrieb");
  });

  it("gives nothing for an empty link", () => {
    expect(descriptionHref(undefined)).toBeUndefined();
  });
});

describe("descriptionImage", () => {
  it("serves the pictures from public/projekt/", () => {
    expect(descriptionImage("assets/projekt/start.png")).toBe("/projekt/start.png");
  });

  it("refuses anything else - the app shows only its own copied pictures", () => {
    expect(descriptionImage("https://example.org/x.png")).toBeUndefined();
    expect(descriptionImage("assets/projekt/../../secret.png")).toBeUndefined();
    expect(descriptionImage(undefined)).toBeUndefined();
  });
});
