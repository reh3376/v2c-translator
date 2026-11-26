/**
 * Takes the screenshots in `web/docs/screenshots/`.
 *
 * The report shots answer `/api/translate` from `src/engine/fixtures/army-report.json`, so this
 * runs without a built O*NET index and without any real service record.
 *
 * Each page is shot in both themes: the light ones with the system as it comes, the `-dark` ones
 * with the system set to dark and the appearance control left on System.
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

async function shoot(browser, name, { width, height, report: withReport = false, reducedMotion, colorScheme }) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion, colorScheme });
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

/** Where down the page a strip is shot, as a percentage of what there is to scroll. */
const STOPS = [0, 25, 50, 75, 100];

const BRANCHES = ["Navy", "Coast Guard", "Marine Corps", "Army", "Air Force", "Space Force"];

const scrollTo = (page, at) =>
  page.evaluate((stop) => {
    window.scrollTo(0, Math.round(((document.documentElement.scrollHeight - window.innerHeight) * stop) / 100));
  }, at);

/**
 * The page at five points on the way down, in one theme and at one width.
 *
 * A scrolling page has no single state: the planes of the branch pictures, the three steps of
 * "How it works" and the report's sticky summary all look different at different points, and the
 * failures live between the two frames you happened to look at.
 */
async function strip(browser, name, { width, height, reducedMotion, colorScheme }) {
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion, colorScheme });
  const page = await context.newPage();
  await stubTranslate(page);
  await page.goto(baseURL, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Try with sample documents" }).click();
  await page.getByRole("heading", { name: "Civilian keywords", exact: true }).waitFor();
  await settle(page);

  for (const stop of STOPS) {
    await scrollTo(page, stop);
    await page.waitForTimeout(500);
    const path = join(out, `strip-${name}-${String(stop).padStart(3, "0")}.png`);
    await page.screenshot({ path });
    console.log(`wrote ${path}`);
  }
  await context.close();
}

/**
 * Each branch's vignette, caught while it is playing.
 *
 * Nothing plays on its own, so each one is pressed. The moments are chosen to land after the
 * first actor has settled and while the last is still arriving.
 */
async function scenes(browser, name, { colorScheme, reducedMotion, at }) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme, reducedMotion });
  const page = await context.newPage();
  await page.goto(baseURL, { waitUntil: "networkidle" });
  await settle(page);

  for (const branch of BRANCHES) {
    const tile = page.getByRole("button", { name: `Play the ${branch} scene` });
    await tile.click();
    let waited = 0;
    for (const [index, moment] of at.entries()) {
      await page.waitForTimeout(moment - waited);
      waited = moment;
      const path = join(out, `scene-${branch.toLowerCase().replace(/ /g, "-")}-${name}-${index + 1}.png`);
      await tile.screenshot({ path });
      console.log(`wrote ${path}`);
    }
    await page.waitForTimeout(3400);
  }
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

  // The same page with the system set to dark. The appearance control is left on System, so
  // these are what a reader gets without touching anything.
  const dark = { colorScheme: "dark" };
  await shoot(browser, "desktop-empty-dark", { width: 1440, height: 900, ...dark });
  await shoot(browser, "desktop-report-dark", { width: 1440, height: 900, report: true, ...dark });
  await shoot(browser, "mobile-report-dark", { width: 390, height: 844, report: true, ...dark });

  // The scroll strips: the whole page, top to bottom, with a report on it.
  await strip(browser, "desktop-light", { width: 1440, height: 900 });
  await strip(browser, "desktop-dark", { width: 1440, height: 900, ...dark });
  await strip(browser, "mobile-light", { width: 390, height: 844 });
  await strip(browser, "reduced-light", { width: 1440, height: 900, reducedMotion: "reduce" });
  await strip(browser, "reduced-dark", { width: 1440, height: 900, reducedMotion: "reduce", ...dark });

  // The six scenes, two moments each, in both themes, and the still frame a reader who asked for
  // less motion gets instead.
  await scenes(browser, "light", { at: [1000, 1700, 2500] });
  await scenes(browser, "dark", { ...dark, at: [1400, 2300] });
  await scenes(browser, "reduced", { reducedMotion: "reduce", at: [900] });
} finally {
  await browser.close();
}
