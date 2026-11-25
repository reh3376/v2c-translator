import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

const index = process.env.DD214KW_INDEX;
test.skip(!index || !existsSync(index), "needs a built index at $DD214KW_INDEX");

test("translates the sample documents into a report", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Try with sample documents" }).click();

  await expect(page.getByRole("heading", { name: "Civilian keywords", exact: true })).toBeFocused();
  const specialties = page.getByRole("table");
  await expect(specialties.getByRole("row", { name: /11B30 INFANTRYMAN/ })).toContainText("11B Infantryman");
  await expect(specialties.getByRole("row", { name: /92Y20 UNIT SUPPLY SPECIALIST/ })).toContainText(
    "92Y Unit Supply Specialist",
  );
  await expect(page.getByRole("region", { name: "Experience" })).toContainText("9+ Years Professional Experience");

  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

  const markdownDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Markdown" }).click();
  expect((await markdownDownload).suggestedFilename()).toBe(`army_2000-civilian-keywords-${today}.md`);
  const markdown = await readFile(await (await markdownDownload).path(), "utf8");
  expect(markdown).toContain("| 11B30 INFANTRYMAN 6 YRS 4 MOS | 11B Infantryman |");

  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download JSON" }).click();
  expect((await jsonDownload).suggestedFilename()).toBe(`army_2000-civilian-keywords-${today}.json`);
});

test("names a file the translator can't read", async ({ page }) => {
  await page.goto("/");
  await page.locator("input[type=file]").setInputFiles({
    name: "hello.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("hello"),
  });
  await page.getByRole("button", { name: "Translate 1 document" }).click();

  const alert = page.getByRole("alert").filter({ hasText: "Couldn't read" });
  await expect(alert).toContainText("Couldn't read hello.txt");
  await expect(alert).toContainText("Unrecognised document");
});
