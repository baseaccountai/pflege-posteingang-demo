// @vitest-environment node
// F11-AC1: installable on Android (manifest) and iOS (apple-touch-icon, web app meta).
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

import manifest from "@/app/manifest";

// The layout loads its fonts through the Next.js build; not needed for its metadata.
vi.mock("next/font/google", () => ({ Geist: () => ({ variable: "" }), Geist_Mono: () => ({ variable: "" }) }));

const PUBLIC = path.resolve(__dirname, "../../../public");

/** Width and height from the IHDR chunk of a PNG file. */
function pngSize(file: string): [number, number] {
  const data = readFileSync(path.join(PUBLIC, file));
  expect(data.subarray(1, 4).toString()).toBe("PNG");
  return [data.readUInt32BE(16), data.readUInt32BE(20)];
}

describe("web app manifest", () => {
  const m = manifest();

  it("names the app and opens standalone in petrol", () => {
    expect(m.name).toBe("Pflege-Posteingang");
    expect(m.short_name).toBe("Posteingang");
    expect(m.display).toBe("standalone");
    expect(m.start_url).toBe("/");
    expect(m.theme_color).toBe("#115e59");
    expect(m.lang).toBe("de");
  });

  it("has icons of 192 and 512 px, also maskable, and the files have these sizes", () => {
    const icons = m.icons ?? [];
    for (const size of [192, 512]) {
      const any = icons.find((i) => i.sizes === `${size}x${size}` && i.purpose === "any");
      const maskable = icons.find((i) => i.sizes === `${size}x${size}` && i.purpose === "maskable");
      expect(any && maskable, `${size}`).toBeTruthy();
      for (const icon of [any!, maskable!]) {
        expect(icon.type).toBe("image/png");
        expect(pngSize(icon.src)).toEqual([size, size]);
      }
    }
  });
});

describe("iOS", () => {
  it("has an apple touch icon of 180 px", () => {
    expect(pngSize("/icons/apple-touch-icon.png")).toEqual([180, 180]);
  });

  it("is declared as web app with the theme colour", async () => {
    const { metadata, viewport } = await import("@/app/layout");
    expect(metadata.appleWebApp).toMatchObject({ capable: true, title: "Posteingang" });
    expect(metadata.icons).toMatchObject({ apple: "/icons/apple-touch-icon.png" });
    expect(viewport.themeColor).toBe("#115e59");
  });
});
