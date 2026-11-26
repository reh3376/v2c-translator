import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { BRANCH_NAMES } from "../src/content/branches";

/**
 * The scroll-driven page: the layered branch pictures, the vignette each one plays, the three
 * steps of "How it works", and the report's sticky summary.
 *
 * These answer `/api/translate` from the fixture report, so they need no built index and touch
 * no real document.
 */

const MARKDOWN = "# Civilian Workforce Keywords\n";
const FIXTURE = join(process.cwd(), "src/engine/fixtures/army-report.json");

async function stubTranslate(page: Page) {
  const report = JSON.parse(await readFile(FIXTURE, "utf8"));
  await page.route("**/api/translate", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, report, markdown: MARKDOWN }),
    }),
  );
}

async function showReport(page: Page) {
  await page.getByRole("button", { name: "Try with sample documents" }).click();
  await expect(page.getByRole("heading", { name: "Civilian keywords", exact: true })).toBeVisible();
}

/** Walk the whole page in steps a reader would take, and wait for each to settle. */
async function scrollThrough(page: Page, steps = 12) {
  for (let i = 0; i <= steps; i += 1) {
    await page.evaluate((at) => {
      const height = document.documentElement.scrollHeight - window.innerHeight;
      window.scrollTo(0, Math.round((height * at) / 12));
    }, i);
    await page.waitForTimeout(90);
  }
}

const tile = (page: Page, branch: string) => page.getByRole("button", { name: `Play the ${branch} scene` });

test("gives every branch picture a button that plays its scene once and settles back", async ({ page }) => {
  await page.goto("/");

  for (const branch of BRANCH_NAMES) {
    await expect(tile(page, branch), branch).toHaveAttribute("data-state", "rest");
  }

  const navy = tile(page, "Navy");
  await navy.click();
  await expect(navy).toHaveAttribute("data-state", "playing");

  // The others are untouched by it, and starting one does not stop another.
  const army = tile(page, "Army");
  await army.click();
  await expect(army).toHaveAttribute("data-state", "playing");
  await expect(navy).toHaveAttribute("data-state", "playing");

  await expect(navy).toHaveAttribute("data-state", "rest", { timeout: 6000 });
  await expect(army).toHaveAttribute("data-state", "rest", { timeout: 6000 });
});

test("plays a scene from the keyboard, and plays it again when asked again", async ({ page }) => {
  await page.goto("/");
  const sf = tile(page, "Space Force");

  await sf.focus();
  await expect(sf).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(sf).toHaveAttribute("data-state", "playing");
  await expect(sf).toHaveAttribute("data-state", "rest", { timeout: 6000 });

  await page.keyboard.press("Space");
  await expect(sf).toHaveAttribute("data-state", "playing");
  await expect(sf).toBeFocused();
});

test("keeps one description per picture, however many layers it is drawn in", async ({ page }) => {
  await page.goto("/");
  const band = page.getByRole("region", { name: "The six services" });
  await expect(band.getByRole("img")).toHaveCount(BRANCH_NAMES.length);
  await expect(band.getByRole("img").first()).toHaveAttribute("aria-label", /warship/i);
});

test("moves nothing when the reader asks for less motion", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto("/");
  await scrollThrough(page, 4);

  // The planes of the hero are drawn, stacked, and still.
  const planes = page.locator(".band-panel").first().locator(".plane");
  await expect(planes).toHaveCount(3);
  for (const transform of await planes.evaluateAll((nodes) =>
    nodes.map((node) => getComputedStyle(node).transform),
  )) {
    expect(transform).toBe("none");
  }

  // The three steps of the story are readable, and nothing in them is transformed away.
  const story = page.getByRole("region", { name: "How it works" });
  await story.scrollIntoViewIfNeeded();
  for (const step of ["Add your documents", "Read block by block", "Get your keywords"]) {
    await expect(story.getByRole("heading", { name: step })).toBeVisible();
  }
  const cells = story.locator(".form-cell");
  await expect(cells).toHaveCount(24);
  for (const transform of await cells.evaluateAll((nodes) => nodes.map((n) => getComputedStyle(n).transform))) {
    expect(transform).toBe("none");
  }

  // A scene still plays, as a fade rather than as movement.
  const navy = tile(page, "Navy");
  await navy.scrollIntoViewIfNeeded();
  await navy.click();
  await expect(navy).toHaveAttribute("data-state", "playing");
  await page.waitForTimeout(700);
  const actors = navy.locator(".actor");
  expect(await actors.count()).toBeGreaterThan(0);
  for (const transform of await actors.evaluateAll((nodes) => nodes.map((n) => getComputedStyle(n).transform))) {
    expect(transform).toBe("none");
  }
  await expect(navy).toHaveAttribute("data-state", "rest", { timeout: 6000 });

  await context.close();
});

test("says everything it has to say with no JavaScript at all", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("/");

  const story = page.getByRole("region", { name: "How it works" });
  for (const step of ["Add your documents", "Read block by block", "Get your keywords"]) {
    await expect(story.getByRole("heading", { name: step })).toBeVisible();
  }

  // Nothing is waiting on an animation that will never run.
  for (const selector of [".doc", ".form-cell", ".keyword-line", ".band-art"]) {
    const nodes = page.locator(selector);
    expect(await nodes.count(), selector).toBeGreaterThan(0);
    for (const opacity of await nodes.evaluateAll((all) => all.map((n) => getComputedStyle(n).opacity))) {
      expect(Number(opacity), selector).toBeGreaterThan(0.9);
    }
  }

  await context.close();
});

test("asks no other site for anything, however far the reader scrolls", async ({ page, baseURL }) => {
  const elsewhere: string[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith(baseURL ?? "")) elsewhere.push(request.url());
  });

  await stubTranslate(page);
  await page.goto("/");
  await scrollThrough(page);
  for (const branch of BRANCH_NAMES) await tile(page, branch).click();
  await page.waitForTimeout(1200);
  await showReport(page);
  await scrollThrough(page);

  expect(elsewhere).toEqual([]);
});

test("shifts no layout while the whole page is scrolled", async ({ page }) => {
  await stubTranslate(page);
  await page.addInitScript(() => {
    const scores: { value: number }[] = [];
    Object.assign(window, { __shift: scores });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (!shift.hadRecentInput) scores.push({ value: shift.value });
      }
    }).observe({ type: "layout-shift", buffered: true });
  });

  await page.goto("/");
  await scrollThrough(page);
  await showReport(page);
  await scrollThrough(page);

  const shift = await page.evaluate(() =>
    ((window as unknown as { __shift: { value: number }[] }).__shift ?? []).reduce((all, one) => all + one.value, 0),
  );
  console.log(`cumulative layout shift over a full scroll: ${shift.toFixed(4)}`);
  expect(shift).toBeLessThan(0.1);
});

test("keeps the summary at the top of the report, and out of the keyboard's way", async ({ page }) => {
  await stubTranslate(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await showReport(page);

  const summary = page.locator(".summary");
  await page.getByRole("heading", { name: "Keyword string for job applications" }).scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);

  // It is still on screen, at the top, with the rest of the report scrolled under it.
  const stuck = await summary.boundingBox();
  expect(stuck?.y ?? -1).toBeLessThanOrEqual(1);
  await expect(summary).toContainText("Army");

  // Tabbing back to a download button brings it into view, not under the summary.
  const download = page.getByRole("button", { name: "Download Markdown" });
  await download.focus();
  await page.waitForTimeout(150);
  const button = await download.boundingBox();
  const panel = await summary.boundingBox();
  expect(button).not.toBeNull();
  expect(button!.y).toBeGreaterThanOrEqual(0);
  expect(button!.y + button!.height).toBeLessThanOrEqual((panel?.y ?? 0) + 1);
  await expect(download).toBeFocused();
});

test("leaves the summary in the flow on a phone, where it would take half the screen", async ({
  browser,
}: {
  browser: Browser;
}) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await stubTranslate(page);
  await page.goto("/");
  await showReport(page);

  expect(await page.locator(".summary").evaluate((node) => getComputedStyle(node).position)).toBe("static");
  await context.close();
});
