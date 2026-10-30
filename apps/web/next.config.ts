import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image.
  output: "standalone",
  // No cacheComponents/partial prerendering: a per-request CSP nonce needs every page
  // rendered per request - a prerendered static shell cannot carry the nonce (F11-AC11,
  // Next.js guide "Content Security Policy").
  async headers() {
    return [
      {
        // F11-AC11, all paths. The page CSP with its nonce comes from src/proxy.ts.
        source: "/:path*",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Camera only for this app (photo upload); nothing else.
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(), payment=(), usb=()" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
      {
        // The original next to the review form is framed by this app's own page (F03-AC4);
        // nobody else may frame it. Comes after the entry above, so these values win.
        source: "/api/documents/:id/file",
        headers: [
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'self'" },
        ],
      },
      {
        // The static offline page: no scripts at all, its own inline styles only.
        source: "/offline.html",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
          },
        ],
      },
      {
        // The service worker must never be cached by the browser, or a fix would not
        // reach the visitors (F11, ADR 0008).
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
