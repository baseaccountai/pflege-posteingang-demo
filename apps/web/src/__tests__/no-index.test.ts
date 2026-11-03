// F11-AC22: the demo stays out of search engines. The header covers every path (pages,
// sample PDFs, icons); the meta tag is on every page (checked in e2e/security-headers).
import { describe, expect, it, vi } from "vitest";

// next/font only works inside the Next.js build; the layout needs just a class name here.
vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "font-sans" }),
  Geist_Mono: () => ({ variable: "font-mono" }),
}));

import nextConfig from "../../next.config";
import { metadata } from "../app/layout";

describe("noindex", () => {
  it("sends X-Robots-Tag on all paths", async () => {
    const rules = await nextConfig.headers!();
    const all = rules.find((rule) => rule.source === "/:path*")!;
    expect(all.headers).toContainEqual({ key: "X-Robots-Tag", value: "noindex, nofollow" });
  });

  it("asks robots not to index or follow on every page", () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
