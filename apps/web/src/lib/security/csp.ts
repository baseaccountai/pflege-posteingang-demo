// F11-AC11: Content-Security-Policy of the app pages. Scripts run only from this origin
// with the nonce of the current response ('strict-dynamic' lets them load the build's
// chunks); no eval, no inline scripts - injected markup cannot run code.

/** The CSP for one response; `issuer` is OIDC_ISSUER (login and logout redirect there). */
export function contentSecurityPolicy(nonce: string, issuer: string | undefined, dev = false): string {
  const idp = issuer ? ` ${new URL(issuer).origin}` : "";
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}'`,
    "img-src 'self' blob: data:", // blob: photo preview before upload
    "font-src 'self'",
    "connect-src 'self'",
    "frame-src 'self'", // the original document next to the review form
    "worker-src 'self'", // service worker (ADR 0008)
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    `form-action 'self'${idp}`,
    "frame-ancestors 'none'",
  ].join("; ");
}
