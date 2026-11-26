import { expect, test, type Page } from "@playwright/test";

/**
 * Light, dark, and the choice between them.
 *
 * The colours themselves are checked by `src/theme/contrast.test.ts`, which measures every pair
 * against WCAG AA. What is left to check in a browser is the part a unit test cannot see: which
 * theme the page is actually painted in, that the choice survives a reload, and that it is
 * applied before the first paint rather than after it.
 */

const DARK_PAGE = "rgb(13, 22, 21)";
const LIGHT_PAGE = "rgb(243, 246, 245)";

const pageBackground = (page: Page) =>
  page.evaluate(() => getComputedStyle(document.body).backgroundColor);

const theme = (page: Page) => page.evaluate(() => document.documentElement.getAttribute("data-theme"));

/** Switching theme cross-fades, so the page arrives at its new colour rather than jumping to it. */
const expectPage = (page: Page, colour: string) => expect.poll(() => pageBackground(page)).toBe(colour);

test("follows the operating system when nobody has chosen", async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: "dark" });
  const page = await context.newPage();
  await page.goto("/");

  await expect(page.getByRole("radio", { name: "System" })).toBeChecked();
  expect(await pageBackground(page)).toBe(DARK_PAGE);

  // The reader changes the system setting while the page is open.
  await page.emulateMedia({ colorScheme: "light" });
  await expectPage(page, LIGHT_PAGE);

  await context.close();
});

test("shows the night drawings in the dark, and only those", async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: "dark" });
  const page = await context.newPage();
  await page.goto("/");

  const band = page.getByRole("region", { name: "The six services" });
  await expect(band.getByRole("img")).toHaveCount(6);
  for (const picture of await band.getByRole("img").all()) {
    await expect(picture).toHaveAttribute("src", /-dark\.svg$/);
  }

  await page.getByRole("radio", { name: "Light" }).check();
  for (const picture of await band.getByRole("img").all()) {
    await expect(picture).toHaveAttribute("src", /(?<!-dark)\.svg$/);
  }

  await context.close();
});

test("keeps the chosen theme across a reload", async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: "light" });
  const page = await context.newPage();
  await page.goto("/");

  await page.getByRole("radio", { name: "Dark" }).check();
  await expectPage(page, DARK_PAGE);

  await page.reload();
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
  expect(await theme(page)).toBe("dark");
  expect(await pageBackground(page)).toBe(DARK_PAGE);

  // And back to the system, which here is light.
  await page.getByRole("radio", { name: "System" }).check();
  await page.reload();
  await expectPage(page, LIGHT_PAGE);

  await context.close();
});

test("applies the stored theme before the page is painted", async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: "light" });
  const page = await context.newPage();

  // The markup the browser receives already carries the script, inside <head>, so the attribute
  // is set while the document is still being parsed rather than after React hydrates.
  const html = await (await page.request.get("/")).text();
  const head = html.slice(0, html.indexOf("<body"));
  expect(head).toContain("v2c-appearance");
  expect(head).toContain('setAttribute("data-theme"');
  expect(html).not.toContain('<html lang="en" data-theme');

  // Watch for the attribute from before the page's own first byte runs, and note how far the
  // document had got when it appeared. "loading" means the parser had not reached the body yet.
  await page.addInitScript(() => {
    window.localStorage.setItem("v2c-appearance", "dark");
    const seen: { state?: DocumentReadyState } = {};
    (window as unknown as { themeSetAt: typeof seen }).themeSetAt = seen;
    new MutationObserver(() => {
      if (!seen.state && document.documentElement?.hasAttribute("data-theme")) seen.state = document.readyState;
    }).observe(document, { attributes: true, subtree: true, attributeFilter: ["data-theme"] });
  });
  await page.goto("/");

  const setAt = await page.evaluate(
    () => (window as unknown as { themeSetAt: { state?: DocumentReadyState } }).themeSetAt.state,
  );
  expect(setAt, "the theme has to be set while the document is still parsing").toBe("loading");
  expect(await theme(page)).toBe("dark");
  expect(await pageBackground(page)).toBe(DARK_PAGE);

  await context.close();
});

test("works from the keyboard, with the focus visible", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("radio", { name: "System" }).focus();
  await expect(page.getByRole("radio", { name: "System" })).toBeFocused();

  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
  expect(await theme(page)).toBe("light");

  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
  await expectPage(page, DARK_PAGE);

  const ring = await page
    .getByRole("radio", { name: "Dark" })
    .evaluate((input) => getComputedStyle(input.nextElementSibling as Element).outlineWidth);
  expect(ring).toBe("3px");
});

test("carries on when the browser refuses to remember anything", async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: "light" });
  const page = await context.newPage();
  await page.addInitScript(() => {
    const refuse = () => {
      throw new DOMException("denied");
    };
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get: () => ({ getItem: refuse, setItem: refuse }),
    });
  });
  await page.goto("/");

  await expect(page.getByRole("radio", { name: "System" })).toBeChecked();
  await page.getByRole("radio", { name: "Dark" }).check();
  await expectPage(page, DARK_PAGE);

  // Nothing was stored, so the next visit follows the system again.
  await page.reload();
  await expectPage(page, LIGHT_PAGE);

  await context.close();
});

test("cross-fades between themes, except for a reader who asks for less motion", async ({ browser }) => {
  /** How long the page spends between themes, with the switching attribute held on. */
  async function fade(reducedMotion: "reduce" | "no-preference") {
    const context = await browser.newContext({ colorScheme: "dark", reducedMotion });
    const page = await context.newPage();
    await page.goto("/");

    await page.getByRole("radio", { name: "Light" }).check();
    await expectPage(page, LIGHT_PAGE);

    const duration = await page.evaluate(() => {
      document.documentElement.setAttribute("data-theme-switching", "");
      return getComputedStyle(document.body).transitionDuration;
    });
    await context.close();
    return duration;
  }

  expect(await fade("no-preference")).toMatch(/^0\.1[0-9]s/);
  expect(await fade("reduce")).toBe("0s");
});
