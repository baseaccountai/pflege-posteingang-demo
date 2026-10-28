"use client";
// F10-AC13: shown instead of a page's content while the API does not answer (cold start on
// Vercel, paused database). Asks /api/status every 5 s and reloads the page once the API is
// ready; after 6 attempts (30 s) it gives up. The sample record works without the API.
import Link from "next/link";
import { useEffect, useState } from "react";

import { reloadPage } from "@/lib/navigation";

const RETRY_MS = 5000;
const MAX_ATTEMPTS = 6;

async function apiIsReady(): Promise<boolean> {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    return response.ok && (await response.json()).ready === true;
  } catch {
    return false;
  }
}

export function ApiStatusBoundary() {
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    let attempts = 0;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const check = async () => {
      attempts += 1;
      if (await apiIsReady()) return reloadPage();
      if (stopped) return;
      if (attempts >= MAX_ATTEMPTS) setGaveUp(true);
      else timer = setTimeout(check, RETRY_MS);
    };
    timer = setTimeout(check, RETRY_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, []);

  return (
    <div role="status" className="flex flex-col gap-2 rounded-lg border border-sky-300 bg-sky-50 p-4 text-sky-950">
      <p className="font-medium">
        {gaveUp ? "Demo gerade nicht erreichbar – bitte später erneut versuchen." : "Demo startet gerade … (bis zu 30 Sekunden)"}
      </p>
      {!gaveUp && <p className="text-sm">Die Seite lädt von selbst neu, sobald die Demo bereit ist.</p>}
      <Link href="/muster" className="self-start text-sm underline">
        Musterakte ansehen
      </Link>
    </div>
  );
}
