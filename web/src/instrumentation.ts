/**
 * Read the environment once, at boot, and end the process here if it is wrong.
 *
 * `register()` runs before the server takes its first request, which makes it the place
 * to find out that a hosted deploy has no Turnstile secret: the rollout should fail in
 * the container's first second rather than serve a page that promises a bot check to an
 * endpoint that performs none. That is the shape of career-site's
 * `config.requireTurnstileInProduction`, and the reason is the same.
 *
 * It calls `process.exit` rather than throwing because a throw is not enough. Next.js
 * 16.4 catches it, prints "An error occurred while loading instrumentation hook" in a
 * loop, and keeps the server up and listening, which is the one outcome this check
 * exists to prevent. Measured against the built image on 2026-11-26: the container
 * stayed up, reported Ready, and only the healthcheck noticed.
 */

import { serverConfig, type ServerConfig } from "@/server/config";

export function register(): void {
  let config: ServerConfig;
  try {
    config = serverConfig();
  } catch (error) {
    console.error(`v2c cannot start: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  }
  // One line, no secrets, no addresses: what a rollout needs to confirm it got the mode
  // it asked for.
  const pages = config.limits.maxPages;
  console.log(
    `v2c ${config.mode} mode: ${config.maxConcurrent} concurrent, queue ${config.queueMax}` +
      `, ${pages === null ? "no page limit" : `${pages} pages per document`}` +
      (config.rateLimit ? `, ${config.rateLimit.max} per ${config.rateLimit.windowMs / 60_000} min per visitor` : ""),
  );
}
