// @vitest-environment node
// F11-AC2, AC3: the real public/sw.js, run in a sandbox. It may store only a fixed list
// (/_next/static/*, /icons/*, /offline.html) and nothing else - no pages, no RSC, no /auth,
// no /api, no documents, no answers. A page without network gets the offline page.
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { describe, expect, it, vi } from "vitest";

const ORIGIN = "https://pflege.example";
const SOURCE = readFileSync(path.resolve(__dirname, "../../../public/sw.js"), "utf8");

type Listener = (event: object) => void;

function loadWorker(network: (request: Request) => Promise<Response>) {
  const listeners: Record<string, Listener> = {};
  const stored = new Map<string, Response>();
  const cache = {
    put: vi.fn(async (request: Request | string, response: Response) => {
      stored.set(typeof request === "string" ? request : request.url, response);
    }),
    match: vi.fn(async (request: Request | string) => stored.get(typeof request === "string" ? new URL(request, ORIGIN).href : request.url)),
    addAll: vi.fn(async (urls: string[]) => {
      for (const url of urls) stored.set(new URL(url, ORIGIN).href, new Response("offline page"));
    }),
  };
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, listener: Listener) => (listeners[type] = listener),
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
  };
  const context = {
    self,
    caches: { open: vi.fn(async () => cache), keys: vi.fn(async () => []), delete: vi.fn() },
    fetch: vi.fn(network),
    URL,
    Response,
  };
  vm.runInNewContext(SOURCE, context);
  return { listeners, stored, context };
}

async function fetchEvent(worker: ReturnType<typeof loadWorker>, url: string, init: { mode?: string; method?: string } = {}) {
  let answer: Promise<Response> | undefined;
  const request = { url: new URL(url, ORIGIN).href, method: init.method ?? "GET", mode: init.mode ?? "no-cors" } as unknown as Request;
  worker.listeners.fetch({ request, respondWith: (promise: Promise<Response>) => (answer = promise), waitUntil: () => {} });
  return answer ? await answer : undefined;
}

const ok = async () => new Response("from network");
const offline = async (): Promise<Response> => {
  throw new TypeError("offline");
};

describe("service worker", () => {
  it.each(["/_next/static/chunks/app-123.js", "/_next/static/css/a.css", "/icons/icon-192.png"])(
    "stores %s and serves it from the cache afterwards",
    async (url) => {
      const worker = loadWorker(ok);
      expect(await (await fetchEvent(worker, url))!.text()).toBe("from network");
      expect(worker.stored.has(new URL(url, ORIGIN).href)).toBe(true);
      worker.context.fetch.mockClear();
      await fetchEvent(worker, url);
      expect(worker.context.fetch).not.toHaveBeenCalled(); // cache first
    },
  );

  it.each(["/", "/bewohner", "/auth/callback?code=x", "/fragen?bewohner=r1"])(
    "passes the page %s through to the network and stores nothing",
    async (url) => {
      const worker = loadWorker(ok);
      expect(await (await fetchEvent(worker, url, { mode: "navigate" }))!.text()).toBe("from network");
      expect(worker.stored.size).toBe(0);
    },
  );

  it.each([
    ["/bewohner/r1?_rsc=abc", "cors"],
    ["/api/documents/d1/file", "no-cors"],
    ["/api/questions", "cors"],
    ["/muster/5eed.pdf", "no-cors"],
    ["/manifest.webmanifest", "no-cors"],
    ["https://cdn.example/_next/static/x.js", "no-cors"],
  ])("leaves %s to the browser and stores nothing", async (url, mode) => {
    const worker = loadWorker(ok);
    expect(await fetchEvent(worker, url, { mode })).toBeUndefined(); // no respondWith
    expect(worker.stored.size).toBe(0);
  });

  it("never stores writes, even to an allowed path", async () => {
    const worker = loadWorker(ok);
    expect(await fetchEvent(worker, "/_next/static/x.js", { method: "POST" })).toBeUndefined();
    expect(worker.stored.size).toBe(0);
  });

  it("prepares only the offline page on install", async () => {
    const worker = loadWorker(ok);
    let done: Promise<unknown> = Promise.resolve();
    worker.listeners.install({ waitUntil: (p: Promise<unknown>) => (done = p) });
    await done;
    expect([...worker.stored.keys()]).toEqual([`${ORIGIN}/offline.html`]);
  });

  it("shows the offline page when a page cannot be loaded", async () => {
    const worker = loadWorker(offline);
    let done: Promise<unknown> = Promise.resolve();
    worker.listeners.install({ waitUntil: (p: Promise<unknown>) => (done = p) });
    await done;
    const page = await fetchEvent(worker, "/bewohner", { mode: "navigate" });
    expect(await page!.text()).toBe("offline page");
  });
});

describe("offline page", () => {
  const html = readFileSync(path.resolve(__dirname, "../../../public/offline.html"), "utf8");

  it("says that the demo needs internet, with banner and footer, without scripts", () => {
    expect(html).toContain("Keine Verbindung – die Demo braucht Internet");
    expect(html).toContain("MUSTERDATEN · keine echten Personen");
    expect(html).toContain("Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt");
    expect(html).not.toMatch(/<script/i);
    expect(html).toContain('lang="de"');
  });
});
