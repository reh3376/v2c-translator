import type { NextConfig } from "next";

/**
 * The path the app is served under. Empty for local development, which keeps
 * `pnpm dev` at http://localhost:3009/ exactly as it was. The container is built with
 * `/v2c`, because that is where the career site publishes it.
 *
 * This is the one setting that cannot be moved to boot time: Next.js resolves `basePath`
 * while it writes the client manifests and the router's route table, so it belongs to the
 * build. Passing it through `env` replaces `process.env.V2C_BASE_PATH` in the server and
 * the client bundle alike, which is how `src/base-path.ts` can prefix a raw `fetch` or an
 * unoptimized image without the container having to set the variable again.
 */
const basePath = process.env.V2C_BASE_PATH?.replace(/\/$/, "") ?? "";

const nextConfig: NextConfig = {
  agentRules: false,
  poweredByHeader: false,
  // `node server.js` with only the files it needs, which is what the image runs. Set by
  // the Dockerfile and nowhere else: Next.js warns that `next start` does not work with
  // a standalone build, and `next start` is what README and web/TESTING.md tell a
  // developer to run.
  output: process.env.V2C_STANDALONE === "1" ? "standalone" : undefined,
  basePath: basePath || undefined,
  env: { V2C_BASE_PATH: basePath },
  // The security headers, the Content-Security-Policy among them, are set by
  // `src/middleware.ts` instead of here. `headers()` is evaluated once while the app is
  // built and baked into the routes manifest, and hosted mode has to add what Turnstile
  // needs to the policy at request time, from an environment variable the build has
  // never seen.
};

export default nextConfig;
