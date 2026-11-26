/**
 * Read the environment once, at boot, and die here if it is wrong.
 *
 * `register()` runs before the server takes its first request. Parsing the config here
 * means a hosted deploy missing a Turnstile key fails the rollout, loudly, in the
 * container's first second, instead of serving a page that promises a bot check and an
 * endpoint that performs none. That is the shape of career-site's
 * `config.requireTurnstileInProduction`, and the reason is the same.
 */

import { serverConfig } from "@/server/config";

export function register(): void {
  const config = serverConfig();
  // One line, no secrets, no addresses: what a rollout needs to confirm it got the mode
  // it asked for.
  console.log(
    `v2c ${config.mode} mode: ${config.maxConcurrent} concurrent, queue ${config.queueMax}` +
      (config.rateLimit ? `, ${config.rateLimit.max} per ${config.rateLimit.windowMs / 60_000} min per visitor` : ""),
  );
}
