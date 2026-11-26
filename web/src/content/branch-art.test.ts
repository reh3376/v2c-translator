import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  actPictures,
  BRANCH_DIR,
  DERIVED_DIR,
  expectedArt,
  layersOf,
  layerSvg,
  lightPictures,
  orphans,
  PLANES as GENERATED_PLANES,
  strengthFor,
  topLevel,
} from "../../scripts/dark-art.mjs";
import { actorArt, BRANCH_PANELS, planeArt, PLANES } from "./branches";
import { VIGNETTES } from "./vignettes";

/**
 * Everything the page shows of the branch pictures is generated, not drawn, so what is worth
 * testing is that the files in the repository are what the generator produces from the drawings
 * today, that the planes stack back into the drawing they were cut from, and that every file the
 * page asks for is one of them.
 *
 * What is drawn is a matter for the eye: `web/TESTING.md` walks the six scenes.
 */

const read = (dir: string, file: string) => readFile(join(dir, file), "utf8");
const fileOf = (path: string) => path.split("/").pop() ?? "";
const withoutColour = (svg: string) => svg.replace(/#[0-9a-f]{6}\b/gi, "#000000");
const shapesOf = (svg: string) => topLevel(svg).children.filter((chunk: string) => !chunk.startsWith("<defs"));
const actFile = (panel: { illustration: string }) => fileOf(panel.illustration).replace(".svg", "-act.svg");

describe("the derived branch pictures", () => {
  it("are the committed output of scripts/dark-art.mjs", async () => {
    const expected = await expectedArt();
    for (const [file, contents] of expected) {
      const onDisk = await read(DERIVED_DIR, file).catch(() => "");
      expect(onDisk, `${file} is stale: run pnpm dark-art`).toBe(contents);
    }
  });

  it("leave nothing behind that no drawing derives any more", async () => {
    expect(await orphans(await expectedArt()), "run pnpm dark-art").toEqual([]);
  });

  it("cover every drawing, and nothing else", async () => {
    expect((await lightPictures()).sort()).toEqual(BRANCH_PANELS.map((panel) => fileOf(panel.illustration)).sort());
    expect((await actPictures()).sort()).toEqual(BRANCH_PANELS.map(actFile).sort());
  });

  it("change only the colours after dark, so no shape and no description can drift", async () => {
    for (const panel of BRANCH_PANELS) {
      const day = await read(BRANCH_DIR, fileOf(panel.illustration));
      const night = await read(DERIVED_DIR, fileOf(panel.illustrationDark));
      expect(withoutColour(night), panel.name).toBe(withoutColour(day));
    }
  });

  it("take the two drawings that need it gently, and every other one at full strength", () => {
    expect(strengthFor("navy")).toBe(1);
    // Already a night scene.
    expect(strengthFor("space-force")).toBeLessThan(strengthFor("navy"));
    // White smoke against the sky: at full strength the two meet and the puffs disappear.
    expect(strengthFor("navy-act")).toBeLessThan(strengthFor("navy"));
  });
});

describe("the depth planes", () => {
  it("hold every shape of the drawing between them, each exactly once", async () => {
    for (const panel of BRANCH_PANELS) {
      const drawing = await read(BRANCH_DIR, fileOf(panel.illustration));
      const cut = PLANES.flatMap((plane) => shapesOf(layerSvg(drawing, "data-plane", plane)));
      expect([...cut].sort(), panel.name).toEqual([...shapesOf(drawing)].sort());
    }
  });

  it("are the planes the generator cuts", () => {
    expect([...PLANES]).toEqual(GENERATED_PLANES);
  });

  it("keep the whole frame, so the three stack back into the picture", async () => {
    for (const panel of BRANCH_PANELS) {
      const frame = /viewBox="[^"]*"/.exec(await read(BRANCH_DIR, fileOf(panel.illustration)))?.[0];
      for (const plane of PLANES) {
        const art = await read(DERIVED_DIR, fileOf(planeArt(panel, plane).day));
        expect(art, `${panel.name} ${plane}`).toContain(frame);
      }
    }
  });

  it("carry no description of their own, because the stage they sit in has one", async () => {
    for (const panel of BRANCH_PANELS) {
      for (const plane of PLANES) {
        const art = await read(DERIVED_DIR, fileOf(planeArt(panel, plane).day));
        expect(art, `${panel.name} ${plane}`).not.toContain("aria-label");
      }
    }
  });
});

describe("the vignette actors", () => {
  it("have a drawing, by day and after dark, for every beat of every scene", async () => {
    for (const panel of BRANCH_PANELS) {
      for (const beat of VIGNETTES[panel.name].beats) {
        const art = actorArt(panel, beat.actor);
        for (const path of [art.day, art.night]) {
          const onDisk = await read(DERIVED_DIR, fileOf(path)).catch(() => "");
          expect(onDisk, `${panel.name}: ${path} is missing`).toContain(`data-actor="${beat.actor}"`);
        }
      }
    }
  });

  it("are all played, so no actor is drawn and then left out of its scene", async () => {
    for (const panel of BRANCH_PANELS) {
      const drawn = layersOf(await read(BRANCH_DIR, actFile(panel)), "data-actor");
      const played = VIGNETTES[panel.name].beats.map((beat) => beat.actor);
      expect([...drawn].sort(), panel.name).toEqual([...played].sort());
    }
  });
});
