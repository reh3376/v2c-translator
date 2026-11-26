import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { BRANCH_DIR, expectedDarkPictures, lightPictures, strengthFor } from "../../scripts/dark-art.mjs";
import { BRANCH_PANELS } from "./branches";

/**
 * The dark pictures are generated, not drawn, so the thing worth testing is that the files in
 * the repository are what the generator produces from the light ones today.
 */

describe("the dark branch pictures", () => {
  it("are the committed output of scripts/dark-art.mjs", async () => {
    const expected = await expectedDarkPictures();
    expect(expected.size).toBe(BRANCH_PANELS.length);
    for (const [file, contents] of expected) {
      const onDisk = await readFile(join(BRANCH_DIR, file), "utf8").catch(() => "");
      expect(onDisk, `${file} is stale: run node scripts/dark-art.mjs`).toBe(contents);
    }
  });

  it("cover every light picture, and nothing else", async () => {
    const light = await lightPictures();
    expect(light.sort()).toEqual(BRANCH_PANELS.map((panel) => panel.illustration.split("/").pop()).sort());
  });

  it("change only the colours, so no shape and no description can drift", async () => {
    for (const panel of BRANCH_PANELS) {
      const day = await readFile(join(BRANCH_DIR, panel.illustration.split("/").pop() ?? ""), "utf8");
      const night = await readFile(join(BRANCH_DIR, panel.illustrationDark.split("/").pop() ?? ""), "utf8");
      const withoutColour = (svg: string) => svg.replace(/#[0-9a-f]{6}\b/gi, "#000000");
      expect(withoutColour(night), panel.name).toBe(withoutColour(day));
    }
  });

  it("take Space Force gently, because it is already a night scene", () => {
    expect(strengthFor("space-force")).toBeLessThan(strengthFor("navy"));
    expect(strengthFor("navy")).toBe(1);
  });
});
