/**
 * The security headers, set per request so the Content-Security-Policy can depend on the
 * deploy mode.
 *
 * They used to live in `next.config.ts`. `headers()` there is evaluated once while the
 * app is built and written into the routes manifest, which is fine for a fixed policy
 * and wrong for this one: hosted mode has to allow Cloudflare Turnstile, and the build
 * that makes the image has never seen `V2C_MODE`.
 *
 * The Node.js runtime, not the edge one, because this reads `process.env` at request
 * time and the edge runtime only has what the build inlined.
 */

import { NextResponse } from "next/server";
import { serverConfig } from "@/server/config";
import { securityHeaders } from "@/security-headers";

export const config = {
  runtime: "nodejs",
  // Everything the app serves, including the static assets Next serves itself.
  matcher: "/:path*",
};

export function middleware(): NextResponse {
  const response = NextResponse.next();
  const headers = securityHeaders(serverConfig().mode, {
    dev: process.env.NODE_ENV === "development",
  });
  for (const [name, value] of Object.entries(headers)) response.headers.set(name, value);
  return response;
}
