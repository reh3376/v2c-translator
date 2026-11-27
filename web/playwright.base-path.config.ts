import { defineConfig } from "@playwright/test";

/**
 * The same app, built to be served from `/v2c` instead of the root, which is how the
 * career site publishes it.
 *
 * A separate config rather than a second project, because the difference is in the build
 * and Playwright starts one web server per config. It runs only `base-path.spec.ts`: the
 * rest of the suite is about what the page does, which a prefix does not change, and
 * building twice to find that out again would cost two minutes of every CI run.
 *
 * Local mode, so no Turnstile and no keys. Whether the hosted container works under the
 * prefix is answered by the container smoke test in CI, which hits the real image.
 */

const port = 3219;
const basePath = "/v2c";

// Playwright loads this config in the runner and in every worker, so setting it here is
// how the spec and the web server end up agreeing on the prefix.
process.env.V2C_BASE_PATH = basePath;

export default defineConfig({
  testDir: "e2e",
  testMatch: "base-path.spec.ts",
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://127.0.0.1:${port}`, channel: "chrome", trace: "retain-on-failure" },
  webServer: {
    command: `pnpm build && pnpm start --port ${port}`,
    url: `http://127.0.0.1:${port}${basePath}`,
    env: { V2C_BASE_PATH: basePath },
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
