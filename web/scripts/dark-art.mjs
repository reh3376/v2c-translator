/**
 * Writes the dark-theme branch pictures from the light ones.
 *
 * The six illustrations are flat colour. A dark variant is therefore not a redraw but one
 * transform applied to every colour in the file: move each through OKLCH, pull its lightness
 * into the night band, take some of the chroma out, and leave its hue alone. The transform is
 * monotonic in lightness, so every shape keeps the same order of light and dark it had by day,
 * and nothing in the drawing changes: no outline moves, and no seal, emblem or logo can appear
 * that was not there before.
 *
 * Space Force is already a night scene, so it is barely touched. That is the only piece of art
 * direction here, and it lives in STRENGTH below.
 *
 * Usage, from `web/`:
 *
 *   node scripts/dark-art.mjs           # write web/public/branches/*-dark.svg
 *   node scripts/dark-art.mjs --check   # fail if the committed files are out of date
 *
 * `src/content/branch-art.test.ts` runs the same check, so a light picture that changes without
 * its dark twin fails the test suite.
 */

import { readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** Where a night sky starts, and how much room the whole picture gets above it, in OKLCH L. */
const NIGHT_FLOOR = 0.09;
const NIGHT_SPAN = 0.33;

/** Night takes the edge off a colour without draining it. */
const CHROMA_SCALE = 0.78;
const CHROMA_CEILING = 0.085;

/** How much of the transform each picture gets. 1 is full night. */
const STRENGTH = { "space-force": 0.3 };
const FULL_STRENGTH = 1;

export const strengthFor = (name) => STRENGTH[name] ?? FULL_STRENGTH;

const clamp01 = (value) => Math.min(1, Math.max(0, value));

const toLinear = (value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
const fromLinear = (value) => (value <= 0.0031308 ? value * 12.92 : 1.055 * value ** (1 / 2.4) - 0.055);

/**
 * sRGB hexadecimal to OKLCH. The matrices are Björn Ottosson's, to seven decimals: further
 * places cannot move an eight-bit channel, and a longer run of digits looks to
 * `scripts/pii_guard.py` like an identifier.
 */
export function hexToOklch(hex) {
  const n = Number.parseInt(hex.slice(1), 16);
  const r = toLinear(((n >> 16) & 0xff) / 255);
  const g = toLinear(((n >> 8) & 0xff) / 255);
  const b = toLinear((n & 0xff) / 255);

  const l = Math.cbrt(0.4122215 * r + 0.5363325 * g + 0.051446 * b);
  const m = Math.cbrt(0.2119035 * r + 0.6806995 * g + 0.107397 * b);
  const s = Math.cbrt(0.0883025 * r + 0.2817188 * g + 0.6299787 * b);

  const lightness = 0.2104543 * l + 0.7936178 * m - 0.004072 * s;
  const a = 1.9779985 * l - 2.4285922 * m + 0.4505937 * s;
  const bb = 0.025904 * l + 0.7827718 * m - 0.8086758 * s;

  return { l: lightness, c: Math.hypot(a, bb), h: Math.atan2(bb, a) };
}

/** OKLCH back to a six-digit sRGB hexadecimal, clipped into gamut. */
export function oklchToHex({ l, c, h }) {
  const a = c * Math.cos(h);
  const b = c * Math.sin(h);

  const lCube = (l + 0.3963378 * a + 0.2158038 * b) ** 3;
  const mCube = (l - 0.1055613 * a - 0.0638542 * b) ** 3;
  const sCube = (l - 0.0894842 * a - 1.2914855 * b) ** 3;

  const channels = [
    4.0767417 * lCube - 3.3077116 * mCube + 0.2309699 * sCube,
    -1.268438 * lCube + 2.6097574 * mCube - 0.3413194 * sCube,
    -0.0041961 * lCube - 0.7034186 * mCube + 1.7076147 * sCube,
  ];

  return `#${channels
    .map((channel) => Math.round(clamp01(fromLinear(clamp01(channel))) * 255))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** One colour, taken into the night by `strength` (0 leaves it alone, 1 is the full move). */
export function darkenColor(hex, strength) {
  const { l, c, h } = hexToOklch(hex);
  const night = { l: NIGHT_FLOOR + NIGHT_SPAN * l, c: Math.min(c * CHROMA_SCALE, CHROMA_CEILING), h };
  return oklchToHex({ l: l + strength * (night.l - l), c: c + strength * (night.c - c), h });
}

/** The same drawing, after dark. Only the colours change. */
export function darkenSvg(svg, strength) {
  return svg.replace(/#[0-9a-f]{6}\b/gi, (hex) => darkenColor(hex.toLowerCase(), strength));
}

export const darkName = (file) => file.replace(/\.svg$/, "-dark.svg");

const here = dirname(fileURLToPath(import.meta.url));
export const BRANCH_DIR = join(here, "..", "public", "branches");

/** The light pictures, by file name, in a stable order. */
export async function lightPictures() {
  const files = await readdir(BRANCH_DIR);
  return files.filter((file) => file.endsWith(".svg") && !file.endsWith("-dark.svg")).sort();
}

/** What each dark file should contain, keyed by its file name. */
export async function expectedDarkPictures() {
  const entries = await Promise.all(
    (await lightPictures()).map(async (file) => {
      const light = await readFile(join(BRANCH_DIR, file), "utf8");
      return [darkName(file), darkenSvg(light, strengthFor(file.replace(/\.svg$/, "")))];
    }),
  );
  return new Map(entries);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const expected = await expectedDarkPictures();
  const checking = process.argv.includes("--check");
  const stale = [];

  for (const [file, contents] of expected) {
    const path = join(BRANCH_DIR, file);
    if (checking) {
      const onDisk = await readFile(path, "utf8").catch(() => "");
      if (onDisk !== contents) stale.push(file);
    } else {
      await writeFile(path, contents);
      console.log(`wrote ${path}`);
    }
  }

  if (stale.length > 0) {
    console.error(`out of date: ${stale.join(", ")}. Run: node scripts/dark-art.mjs`);
    process.exit(1);
  }
  if (checking) console.log(`${expected.size} dark pictures are up to date`);
}
