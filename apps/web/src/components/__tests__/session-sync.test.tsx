// F01-AC13: after logout or role switch in one tab, other tabs leave pages with old data.
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SESSION_CHANNEL, SessionSync, announceSessionEnd } from "@/components/session-sync";

describe("SessionSync", () => {
  const channels: BroadcastChannel[] = [];
  afterEach(() => channels.splice(0).forEach((c) => c.close()));

  it("leaves the page when another tab ends the session", async () => {
    const onEnded = vi.fn();
    render(<SessionSync onEnded={onEnded} />);
    const otherTab = new BroadcastChannel(SESSION_CHANNEL);
    channels.push(otherTab);
    otherTab.postMessage({ ended: "other-tab" });
    await vi.waitFor(() => expect(onEnded).toHaveBeenCalled());
  });

  it("ignores its own announcement (the switching tab must finish its form POST)", async () => {
    const onEnded = vi.fn();
    render(<SessionSync onEnded={onEnded} />);
    const listener = new BroadcastChannel(SESSION_CHANNEL);
    channels.push(listener);
    const received = new Promise((resolve) => (listener.onmessage = resolve));
    announceSessionEnd();
    await received;
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(onEnded).not.toHaveBeenCalled();
  });

  it("announceSessionEnd tells the other tabs", async () => {
    const listener = new BroadcastChannel(SESSION_CHANNEL);
    channels.push(listener);
    const received = new Promise((resolve) => (listener.onmessage = (e) => resolve(e.data)));
    announceSessionEnd();
    expect(await received).toEqual({ ended: expect.any(String) });
  });
});
