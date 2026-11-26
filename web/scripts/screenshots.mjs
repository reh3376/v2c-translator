/**
 * Takes the screenshots in `web/docs/screenshots/`.
 *
 * The report shots answer `/api/translate` from `src/engine/fixtures/army-report.json`, so this
 * runs without a built O*NET index and without any real service record.
 *
 * Usage, from `web/`:
 *
 *   pnpm build && pnpm start          # one terminal
 *   node scripts/screenshots.mjs      # another
 *
 * `BASE_URL` overrides http://127.0.0.1:3009.
 */

import { mkdir, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..");
const out = join(web, "docs", "screenshots");
const baseURL = process.env.BASE_URL ?? "http://127.0.0.1:3009";

const MARKDOWN = "# Civilian Workforce Keywords\n\nA sample report, used for screenshots only.\n";

const report = JSON.parse(await readFile(join(web, "src/engine/fixtures/army-report.json"), "utf8"));

async function stubTranslate(page) {
  await page.route("**/api/translate", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, report, markdown: MARKDOWN }),
    }),
  );
}

/** Let entrances finish, so no shot catches a half-faded section. */
const settle = (page) => page.waitForTimeout(900);

async function shoot(browser, name, { width, height, report: withReport = false, reducedMotion }) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion });
  const page = await context.newPage();
  await stubTranslate(page);
  await page.goto(baseURL, { waitUntil: "networkidle" });

  if (withReport) {
    await page.getByRole("button", { name: "Try with sample documents" }).click();
    await page.getByRole("heading", { name: "Civilian keywords", exact: true }).waitFor();
  }
  await settle(page);

  const path = join(out, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  console.log(`wrote ${path}`);
  await context.close();
}

await mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
try {
  await shoot(browser, "desktop-empty", { width: 1440, height: 900 });
  await shoot(browser, "desktop-report", { width: 1440, height: 900, report: true });
  await shoot(browser, "mobile-empty", { width: 390, height: 844 });
  await shoot(browser, "mobile-report", { width: 390, height: 844, report: true });
  await shoot(browser, "desktop-reduced-motion", { width: 1440, height: 900, report: true, reducedMotion: "reduce" });
} finally {
  await browser.close();
}
