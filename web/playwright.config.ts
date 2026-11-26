import { defineConfig } from "@playwright/test";

const port = 3218;

export default defineConfig({
  testDir: "e2e",
  // `behind-caddy.spec.ts` needs the Docker Compose rig in deploy/behind-caddy, not this
  // config's web server. `deploy/verify-behind-caddy.sh` runs it, with its own config.
  testIgnore: "behind-caddy.spec.ts",
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://127.0.0.1:${port}`, channel: "chrome", trace: "retain-on-failure" },
  webServer: {
    command: `pnpm build && pnpm start --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
