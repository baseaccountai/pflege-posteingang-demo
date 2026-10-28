// F11-AC2: registers public/sw.js. Only in the production build; a failed registration
// (private mode, blocked) is fine - the app works the same without it.
export async function registerServiceWorker(nav: Navigator, env: string | undefined = process.env.NODE_ENV) {
  if (env !== "production" || !("serviceWorker" in nav)) return;
  try {
    await nav.serviceWorker.register("/sw.js", { scope: "/" });
  } catch {
    // no offline page then, nothing else changes
  }
}
