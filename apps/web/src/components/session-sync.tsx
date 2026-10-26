"use client";
// Logout or role switch in one tab: the other tabs of this app leave their pages, so no
// open tab keeps showing data of the previous role (F01-AC13).
import { useEffect } from "react";

export const SESSION_CHANNEL = "pp-session";
// Messages also reach other channel objects in the same tab; this id filters them out,
// so the tab that switches roles is not sent away before its form POST is done.
const TAB_ID = crypto.randomUUID();

/** Called right before the logout / role switch form is sent. */
export function announceSessionEnd() {
  const channel = new BroadcastChannel(SESSION_CHANNEL);
  channel.postMessage({ ended: TAB_ID });
  channel.close();
}

const goToStart = () => window.location.replace("/");

export function SessionSync({ onEnded = goToStart }: { onEnded?: () => void }) {
  useEffect(() => {
    const channel = new BroadcastChannel(SESSION_CHANNEL);
    channel.onmessage = (event) => {
      const from = event.data?.ended;
      if (typeof from === "string" && from !== TAB_ID) onEnded();
    };
    return () => channel.close();
  }, [onEnded]);
  return null;
}

/** Logout button for server components (header): announces the end, then posts. */
export function LogoutForm({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <form method="post" action="/auth/logout" onSubmit={announceSessionEnd}>
      <button type="submit" className={className}>
        {children}
      </button>
    </form>
  );
}
