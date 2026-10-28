"use client";
// Registers the service worker once the page runs in the browser (F11-AC2).
import { useEffect } from "react";

import { registerServiceWorker } from "@/lib/service-worker";

export function ServiceWorker() {
  useEffect(() => {
    void registerServiceWorker(navigator);
  }, []);
  return null;
}
