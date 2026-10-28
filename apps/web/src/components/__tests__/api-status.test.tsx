// F10-AC13: instead of an empty page while the API starts: a notice, a retry every 5 s
// (at most 6), a link to the static sample record, then "Demo gerade nicht erreichbar".
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiStatusBoundary } from "@/components/api-status";

vi.mock("@/lib/navigation", () => ({ reloadPage: vi.fn() }));
import { reloadPage } from "@/lib/navigation";

const status = (ready: boolean) =>
  new Response(JSON.stringify({ ready }), { status: ready ? 200 : 503, headers: { "content-type": "application/json" } });

async function after5s() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("ApiStatusBoundary", () => {
  it("says the demo is starting and links the sample record", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<ApiStatusBoundary />);
    expect(screen.getByRole("status")).toHaveTextContent("Demo startet gerade … (bis zu 30 Sekunden)");
    expect(screen.getByRole("link", { name: "Musterakte ansehen" })).toHaveAttribute("href", "/muster");
  });

  it("asks every 5 s and reloads the page as soon as the API is ready", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(status(false)).mockResolvedValueOnce(status(true));
    vi.stubGlobal("fetch", fetch);
    render(<ApiStatusBoundary />);
    expect(fetch).not.toHaveBeenCalled();
    await after5s();
    expect(fetch).toHaveBeenCalledWith("/api/status", { cache: "no-store" });
    expect(reloadPage).not.toHaveBeenCalled();
    await after5s();
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(reloadPage).toHaveBeenCalledTimes(1);
  });

  it("gives up after 6 attempts and says the demo cannot be reached", async () => {
    const fetch = vi.fn().mockResolvedValue(status(false));
    vi.stubGlobal("fetch", fetch);
    render(<ApiStatusBoundary />);
    for (let i = 0; i < 6; i++) await after5s();
    expect(screen.getByRole("status")).toHaveTextContent("Demo gerade nicht erreichbar");
    expect(screen.getByRole("link", { name: "Musterakte ansehen" })).toBeInTheDocument();
    await after5s();
    expect(fetch).toHaveBeenCalledTimes(6);
    expect(reloadPage).not.toHaveBeenCalled();
  });

  it("counts a failed request as an attempt", async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(status(true));
    vi.stubGlobal("fetch", fetch);
    render(<ApiStatusBoundary />);
    await after5s();
    await after5s();
    expect(reloadPage).toHaveBeenCalledTimes(1);
  });
});
