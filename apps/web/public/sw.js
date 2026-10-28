// Service worker of Pflege-Posteingang (F11-AC2, AC3, ADR 0008) - deliberately minimal.
//
// It stores ONLY files from a fixed list: the build's static files (/_next/static/, their
// names change with every build), the app icons and the offline page. Pages, RSC requests,
// /auth, /api, documents and answers to questions are never stored: they contain data of
// the signed-in role and must not outlive a logout or role switch.
//
// Without network a page request gets the offline page.

const CACHE = "pp-static-v1";
const OFFLINE = "/offline.html";

function cacheable(url) {
  if (url.origin !== self.location.origin) return false;
  return url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/") || url.pathname === OFFLINE;
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const stored = await cache.match(request);
  if (stored) return stored;
  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

async function pageOrOffline(request) {
  try {
    return await fetch(request); // straight from the network, never stored
  } catch {
    return (await caches.open(CACHE)).match(OFFLINE);
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll([OFFLINE]))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  // Old versions of this cache go; the new worker takes over open pages at once.
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return; // writes: browser default
  if (cacheable(new URL(request.url))) {
    event.respondWith(cacheFirst(request));
  } else if (request.mode === "navigate") {
    event.respondWith(pageOrOffline(request));
  }
  // Everything else: no respondWith - the browser asks the network as usual, nothing stored.
});
