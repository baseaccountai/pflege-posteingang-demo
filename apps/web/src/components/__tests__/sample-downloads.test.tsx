// F07-AC14: sample documents to try, including the two with an attack, as downloads.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SAMPLE_DOWNLOADS, SampleDownloads } from "@/components/sample-downloads";

const ROOT = path.resolve(__dirname, "../../../../..");
const sha = (file: string) => createHash("sha256").update(readFileSync(file)).digest("hex");

describe("SampleDownloads", () => {
  it("offers every sample as a download and marks the two attacks", () => {
    render(<SampleDownloads />);
    const links = screen.getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual(SAMPLE_DOWNLOADS.map((s) => `/samples/${s.file}`));
    for (const link of links) expect(link).toHaveAttribute("download");
    expect(screen.getAllByText("enthält einen Angriff")).toHaveLength(2);
  });

  it("serves exact copies of the files in samples/", () => {
    for (const sample of SAMPLE_DOWNLOADS) {
      const original = path.join(ROOT, "samples", sample.file);
      const copy = path.join(ROOT, "apps/web/public/samples", sample.file);
      expect(sha(copy), sample.file).toBe(sha(original));
    }
  });
});
