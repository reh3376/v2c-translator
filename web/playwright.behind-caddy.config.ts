import { defineConfig } from "@playwright/test";

/**
 * The hosted image behind a Caddy configured like the career site's.
 *
 * No `webServer`: `deploy/verify-behind-caddy.sh` brings the rig up with Docker Compose
 * and sets V2C_RIG_URL. Run it through that script, not on its own.
 */

export default defineConfig({
  testDir: "e2e",
  testMatch: "behind-caddy.spec.ts",
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? "github" : "list",
  // Serial, because the last spec spends the rig's per-visitor limit.
  workers: 1,
  use: {
    baseURL: process.env.V2C_RIG_URL ?? "http://127.0.0.1:8080",
    channel: "chrome",
    trace: "retain-on-failure",
  },
});
