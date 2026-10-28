// F11-AC2: the service worker is registered for the whole app - only in the production
// build (in development it would keep stale build files).
import { describe, expect, it, vi } from "vitest";

import { registerServiceWorker } from "@/lib/service-worker";

describe("registerServiceWorker", () => {
  it("registers /sw.js for the whole app in production", async () => {
    const register = vi.fn().mockResolvedValue({});
    await registerServiceWorker({ serviceWorker: { register } } as unknown as Navigator, "production");
    expect(register).toHaveBeenCalledWith("/sw.js", { scope: "/" });
  });

  it("does nothing in development or without service worker support", async () => {
    const register = vi.fn();
    await registerServiceWorker({ serviceWorker: { register } } as unknown as Navigator, "development");
    await registerServiceWorker({} as Navigator, "production");
    expect(register).not.toHaveBeenCalled();
  });

  it("keeps the app working if the registration fails", async () => {
    const register = vi.fn().mockRejectedValue(new Error("blocked"));
    await expect(
      registerServiceWorker({ serviceWorker: { register } } as unknown as Navigator, "production"),
    ).resolves.toBeUndefined();
  });
});
