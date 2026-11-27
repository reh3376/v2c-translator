import { existsSync } from "node:fs";
import { expect, test } from "@playwright/test";

/**
 * The page, served from somewhere other than the root.
 *
 * The hosted deploy publishes this app at `rogerhenley.dev/v2c`, which means every
 * absolute path the browser is given has to carry that prefix. Most of them Next.js
 * rewrites itself. The ones it does not are the ones this catches: a raw `fetch`, and an
 * `unoptimized` `next/image`, whose src is served exactly as written. Before
 * `src/base-path.ts` existed, all thirty-six branch drawings and all three sample files
 * 404'd under a base path and the page still looked like it had loaded.
 *
 * So the assertion is about requests, not about pixels: nothing the page asks for may
 * come back 404. `playwright.base-path.config.ts` runs this against a build made with
 * `V2C_BASE_PATH=/v2c`; the ordinary config runs it at the root, where it is the same
 * check with an empty prefix.
 */

const base = process.env.V2C_BASE_PATH ?? "";
const index = process.env.DD214KW_INDEX;

/** Everything the page asked for and did not get. */
function watchFor404s(page: import("@playwright/test").Page): string[] {
  const missing: string[] = [];
  page.on("response", (response) => {
    if (response.status() === 404) missing.push(`${response.status()} ${response.url()}`);
  });
  return missing;
}

test(`serves the page and its assets under ${base || "the root"}`, async ({ page }) => {
  const missing = watchFor404s(page);

  await page.goto(`${base}/`);
  await expect(page.getByRole("heading", { name: "Translate your service record into civilian keywords" })).toBeVisible();

  // Every chunk, stylesheet and font the first paint needs.
  await page.waitForLoadState("networkidle");
  expect(missing).toEqual([]);
});

test("draws all six branch pictures, every plane of them", async ({ page }) => {
  const missing = watchFor404s(page);

  await page.goto(`${base}/`);
  await page.waitForLoadState("networkidle");

  // Three planes per branch, each in the markup twice as a day and a night drawing: six
  // panels, 36 images. The stylesheet shows one theme's, so only 18 are ever fetched,
  // and the other 18 report a natural width of zero because nothing asked for them.
  const drawings = page.locator(".band-art img");
  await expect(drawings).toHaveCount(36);

  const painted = await drawings.evaluateAll(
    (images) => images.filter((image) => (image as HTMLImageElement).naturalWidth > 0).length,
  );
  expect(painted).toBe(18);
  expect(missing).toEqual([]);
});

test("answers the health check", async ({ page }) => {
  const response = await page.request.get(`${base}/api/healthz`);

  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({ ok: true });
});

test("translates the samples, which the page fetches by path", async ({ page }) => {
  test.skip(!index || !existsSync(index), "needs a built index at $DD214KW_INDEX");
  const missing = watchFor404s(page);

  await page.goto(`${base}/`);
  await page.getByRole("button", { name: "Try with sample documents" }).click();

  await expect(page.getByRole("heading", { name: "Civilian keywords", exact: true })).toBeFocused();
  expect(missing).toEqual([]);
});
