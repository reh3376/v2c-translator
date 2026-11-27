import { expect, test } from "@playwright/test";

/**
 * The hosted page as a browser sees it through the career site's Caddy.
 *
 * Everything else in this suite talks to the Next.js server directly, which is the right
 * way to test what the app does and the wrong way to test one thing: the proxy in front
 * of it sends a Content-Security-Policy of its own. Caddy's `header` directive replaces
 * rather than appends, so which policy the browser enforces depends on how that proxy is
 * configured, and the failure mode is silent either way. Turnstile stops working, no
 * error appears anywhere, and the first person to find out is a veteran whose upload is
 * refused.
 *
 * So this runs against the rig in `deploy/behind-caddy/`, started by
 * `deploy/verify-behind-caddy.sh` once per arrangement, and asserts on what the browser
 * does rather than on what the policies say. The script checks which policy arrived;
 * these check that the page works under whichever it was.
 *
 * **What it cannot check.** The rig uses Cloudflare's always-pass test site key, and that
 * key draws no challenge iframe: the widget fills its hidden field and is done. So
 * `script-src` and `connect-src` are exercised here and `frame-src` is not. That one is
 * covered by `src/security-headers.test.ts` asserting the directive, and by the career
 * site already running a real Turnstile widget on this same origin. The first manual
 * check after the deploy is still that the widget's box appears.
 */

const BASE = "/v2c";
const TOKEN_FIELD = 'input[name="cf-turnstile-response"]';

/** Collects the ways a browser says "a policy stopped me". */
function watch(page: import("@playwright/test").Page) {
  const blocked: string[] = [];
  const failed: string[] = [];
  const fromCloudflare: string[] = [];
  page.on("console", (message) => {
    if (/content security policy|refused to (load|connect|frame)/i.test(message.text())) {
      blocked.push(message.text());
    }
  });
  page.on("pageerror", (error) => blocked.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) => failed.push(`${request.failure()?.errorText} ${request.url()}`));
  page.on("response", (response) => {
    if (response.url().includes("challenges.cloudflare.com")) {
      fromCloudflare.push(`${response.status()} ${response.url()}`);
    }
  });
  return { blocked, failed, fromCloudflare };
}

test("loads the page and the robot check with nothing blocked", async ({ page }) => {
  const seen = watch(page);

  const response = await page.goto(`${BASE}`);
  expect(await response?.headerValue("content-security-policy"), "no policy at all").toBeTruthy();

  await expect(page.getByRole("heading", { name: "What happens to your documents" })).toBeVisible();
  await expect(page.getByText("sent over HTTPS to this server")).toBeVisible();

  // The widget ran and handed the page a token. With the test key that happens without a
  // click, and it can only happen if the policy let Cloudflare's script load and talk
  // back, which is `script-src` and `connect-src` both proved by one assertion.
  await expect(page.locator(TOKEN_FIELD)).toHaveValue(/.+/, { timeout: 30_000 });

  expect(seen.fromCloudflare.length, "the browser never reached Cloudflare").toBeGreaterThan(0);
  expect(
    seen.fromCloudflare.filter((line) => !/^(200|204|302|304) /.test(line)),
    "Cloudflare answered with something unexpected",
  ).toEqual([]);
  expect(seen.blocked, "the browser blocked something").toEqual([]);
  expect(seen.failed, "a request failed outright").toEqual([]);
});

test("translates the samples end to end, through the proxy and the robot check", async ({ page }) => {
  const seen = watch(page);

  await page.goto(`${BASE}`);
  await expect(page.locator(TOKEN_FIELD)).toHaveValue(/.+/, { timeout: 30_000 });

  await page.getByRole("button", { name: "Try with sample documents" }).click();

  await expect(page.getByRole("heading", { name: "Civilian keywords", exact: true })).toBeFocused({ timeout: 60_000 });
  await expect(page.getByRole("table").getByRole("row", { name: /11B30 INFANTRYMAN/ })).toBeVisible();
  expect(seen.blocked).toEqual([]);
});

test("counts the visitor's own address, which only the proxy can supply", async ({ page }) => {
  // The rig sets V2C_RATE_LIMIT=3, and the limiter lives in the container, so the tests
  // above have already spent some of this visitor's allowance. The assertion is the shape
  // rather than the count: translations succeed until one is refused with a 429, and a
  // 429 can only happen if Caddy's X-Real-IP reached the app, because local mode limits
  // nobody and an unproxied hosted request shares one bucket.
  const codes: number[] = [];
  while (codes.length < 5 && codes.at(-1) !== 429) {
    const response = await page.request.post(`${BASE}/api/translate`, {
      multipart: {
        files: { name: "army_2000.txt", mimeType: "text/plain", buffer: Buffer.from("not a form") },
        turnstileToken: "XXXX.DUMMY.TOKEN.XXXX",
      },
    });
    codes.push(response.status());
  }

  expect(codes.at(-1), `got ${codes.join(", ")}`).toBe(429);
  expect(codes.slice(0, -1).filter((code) => code !== 422)).toEqual([]);
});
