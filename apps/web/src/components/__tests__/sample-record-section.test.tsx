// F10-AC14: the sample record renders from the repo file alone - no fetch, so no API and no
// login are needed (it is the fallback while the API sleeps, F10-AC13).
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SampleRecordSection } from "@/components/sample-record-section";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));
vi.mock("@/lib/navigation", () => ({ goTo: vi.fn(), leaveEndedSession: vi.fn() }));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SampleRecordSection", () => {
  it("renders the sample resident without calling fetch", async () => {
    const fetchSpy = vi.fn(() => Promise.reject(new Error("no API in the sample record")));
    vi.stubGlobal("fetch", fetchSpy);
    render(await SampleRecordSection());
    expect(screen.getByRole("heading", { level: 1, name: "Fr. Beispiel" })).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
