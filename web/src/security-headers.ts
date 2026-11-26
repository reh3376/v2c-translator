/**
 * The headers every response carries, and the Content-Security-Policy that is most of
 * the point of them.
 *
 * Local mode is as tight as it has always been: everything comes from this origin and
 * nothing may connect anywhere else, which is what makes "nothing leaves this computer"
 * a claim the browser enforces rather than a sentence on a page.
 *
 * Hosted mode adds exactly three allowances, all for Cloudflare Turnstile and all to the
 * one host it uses. Turnstile needs all three and the omission of any one of them is a
 * silent failure: the loader on `script-src`, the challenge iframe on `frame-src`, and
 * the widget's own requests on `connect-src`. `frame-src` in particular is not optional,
 * because `default-src 'self'` would otherwise block the iframe and the widget renders
 * as a blank box with no error anyone sees.
 *
 * **Two policies, not one.** The career site's Caddy sends its own site-wide CSP. A
 * browser given two `Content-Security-Policy` headers enforces both, so a resource has
 * to be allowed by each of them, and the site's policy does not allow this app's needs.
 * The `/v2c*` handle in that Caddyfile therefore has to replace the site policy for this
 * path, or leave it off and let this one stand. That is written down in `docs/deploy.md`
 * with the block to paste, and the policy below is written to be sufficient on its own.
 */

import type { Mode } from "@/server/config";

const TURNSTILE = "https://challenges.cloudflare.com";

export function contentSecurityPolicy(mode: Mode, { dev = false }: { dev?: boolean } = {}): string {
  const hosted = mode === "hosted";
  return [
    "default-src 'self'",
    // 'unsafe-inline' is what Next's hydration bootstrap and the theme boot script need.
    // 'unsafe-eval' is development only, for the dev server's refresh machinery.
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}${hosted ? ` ${TURNSTILE}` : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    `connect-src 'self'${hosted ? ` ${TURNSTILE}` : ""}`,
    hosted ? `frame-src ${TURNSTILE}` : "frame-src 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function securityHeaders(mode: Mode, options: { dev?: boolean } = {}): Record<string, string> {
  return {
    "content-security-policy": contentSecurityPolicy(mode, options),
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
  };
}
