import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { ALL_LINKS, CRISIS_LINE } from "../src/content/resources";

/**
 * The refreshed page: branch pictures, resource links and motion.
 *
 * These answer `/api/translate` from the fixture report, so unlike `translate.spec.ts` they need
 * no built index and touch no real document.
 */

const MARKDOWN = "# Civilian Workforce Keywords\n";

/** Playwright runs from `web/`, where its config lives. */
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

test("shows one picture per branch, and marks the branch the documents named", async ({ page }) => {
  await stubTranslate(page);
  await page.goto("/");

  const band = page.getByRole("region", { name: "The six services" });
  await expect(band.getByRole("img")).toHaveCount(6);
  for (const name of ["Navy", "Coast Guard", "Marine Corps", "Army", "Air Force", "Space Force"]) {
    await expect(band.getByText(name, { exact: true })).toBeVisible();
  }
  await expect(band.locator("[data-marked]")).toHaveCount(0);

  await showReport(page);

  const marked = band.locator("[data-marked]");
  await expect(marked).toHaveCount(1);
  await expect(marked).toContainText("Army");
  await expect(marked).toContainText("From your documents");
  await expect(band).toContainText("Your documents name the Army");
});

test("offers every resource link, each opening in a new tab with no referrer leak", async ({ page }) => {
  await page.goto("/");
  const resources = page.getByRole("region", { name: "Resources for veterans" });

  for (const href of ALL_LINKS) {
    const link = resources.locator(`a[href="${href}"]`);
    await expect(link, href).toHaveCount(1);
    await expect(link, href).toHaveAttribute("target", "_blank");
    await expect(link, href).toHaveAttribute("rel", /noopener/);
    await expect(link, href).toHaveAttribute("rel", /noreferrer/);
  }

  await expect(resources).toContainText(`Dial ${CRISIS_LINE.dial}, then press ${CRISIS_LINE.press}`);
  await expect(resources).toContainText(`text ${CRISIS_LINE.text}`);
});

test("opens a resource link in a new tab when it is clicked", async ({ page, context }) => {
  await page.goto("/");
  await context.route("**/*", (route) =>
    route.request().url().startsWith("http://127.0.0.1")
      ? route.continue()
      : route.fulfill({ status: 200, contentType: "text/html", body: "<title>elsewhere</title>" }),
  );

  const opened = context.waitForEvent("page");
  await page.getByRole("link", { name: /^Request military service records/ }).click();
  const tab = await opened;
  expect(tab.url()).toBe("https://www.archives.gov/veterans/military-service-records");
});

test("expands the occupations a specialty did not have room for", async ({ page }) => {
  await stubTranslate(page);
  await page.goto("/");
  await showReport(page);

  const more = page.getByRole("button", { name: /^Show \d+ more$/ }).first();
  await expect(more).toHaveAttribute("aria-expanded", "false");
  await more.click();
  await expect(page.getByRole("button", { name: "Show fewer" }).first()).toHaveAttribute("aria-expanded", "true");
});

test("builds the whole report without animation when the reader asks for less motion", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await stubTranslate(page);
  await page.goto("/");
  await showReport(page);

  // Nothing waits on an animation: every part of the report is readable at once.
  const chip = page.getByRole("region", { name: "Experience" }).getByRole("listitem").first();
  await expect(chip).toBeVisible();
  expect(await chip.evaluate((node) => getComputedStyle(node).opacity)).toBe("1");
  expect(await chip.evaluate((node) => getComputedStyle(node).transform)).toBe("none");

  await context.close();
});

test("keeps the keyboard path through the page", async ({ page }) => {
  await stubTranslate(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Try with sample documents" }).focus();
  await page.keyboard.press("Enter");

  await expect(page.getByRole("heading", { name: "Civilian keywords", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Download Markdown" })).toBeFocused();
});
