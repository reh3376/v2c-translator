import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { BRANCH_NAMES, BRANCH_PANELS, panelFor } from "./branches";

const repoFile = (path: string) => fileURLToPath(new URL(`../../../${path}`, import.meta.url));

/** The names `detect_branch` can return, read straight out of the translator's own table. */
function branchesInPython(): string[] {
  const source = readFileSync(repoFile("src/dd214kw/parse.py"), "utf8");
  const table = /^BRANCHES[^=]*=\s*\[(.*?)^\]/ms.exec(source);
  if (!table?.[1]) throw new Error("no BRANCHES table in src/dd214kw/parse.py");
  return [...table[1].matchAll(/^\s*\("([^"]+)",/gm)].map((match) => match[1] as string);
}

describe("the branch pictures", () => {
  it("cover every branch the translator can report, and no others", () => {
    expect([...BRANCH_NAMES].sort()).toEqual(branchesInPython().sort());
  });

  it("are six, one per branch", () => {
    expect(BRANCH_PANELS).toHaveLength(6);
    expect(BRANCH_PANELS.map((panel) => panel.name).sort()).toEqual([...BRANCH_NAMES].sort());
  });

  it("are bundled with the app, so the page loads nothing from another site", () => {
    for (const panel of BRANCH_PANELS) {
      const pictures = panel.photo ? [panel.photo.src] : [panel.illustration, panel.illustrationDark];
      for (const picture of pictures) {
        expect(picture.startsWith("/"), panel.name).toBe(true);
        expect(existsSync(repoFile(`web/public${picture}`)), picture).toBe(true);
      }
    }
  });

  it("describe themselves to anyone who cannot see them", () => {
    for (const panel of BRANCH_PANELS) {
      expect(panel.alt.trim().length, panel.name).toBeGreaterThan(20);
      expect(panel.setting.trim(), panel.name).not.toBe("");
    }
  });

  it("credit a photograph whenever one is used", () => {
    for (const panel of BRANCH_PANELS) {
      if (!panel.photo) continue;
      expect(panel.photo.credit.trim(), panel.name).not.toBe("");
    }
  });

  it("show no service seal, emblem or insignia, and claim none", () => {
    const forbidden = /\b(seal|emblem|insignia|logo|crest|flag|trademark)\b/i;
    for (const panel of BRANCH_PANELS) {
      expect(forbidden.test(panel.alt), panel.name).toBe(false);
      for (const picture of [panel.illustration, panel.illustrationDark]) {
        const svg = readFileSync(repoFile(`web/public${picture}`), "utf8");
        expect(forbidden.test(svg), picture).toBe(false);
      }
    }
  });

  it("are found by the branch name a report carries, and only by that", () => {
    expect(panelFor("Army")?.illustration).toBe("/branches/army.svg");
    expect(panelFor("Army")?.illustrationDark).toBe("/branches/derived/army-dark.svg");
    expect(panelFor("army")).toBeUndefined();
    expect(panelFor(null)).toBeUndefined();
    expect(panelFor(undefined)).toBeUndefined();
    expect(panelFor("Merchant Marine")).toBeUndefined();
  });
});
