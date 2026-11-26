/**
 * Writes every derived branch picture from the six hand-drawn light ones.
 *
 * Two derivations, and this file is the only place either happens.
 *
 * **After dark.** The six illustrations are flat colour, so a dark variant is not a redraw but
 * one transform applied to every colour in the file: move each through OKLCH, pull its lightness
 * into the night band, take some of the chroma out, and leave its hue alone. The transform is
 * monotonic in lightness, so every shape keeps the same order of light and dark it had by day,
 * and nothing in the drawing changes: no outline moves, and no seal, emblem or logo can appear
 * that was not there before.
 *
 * Space Force is already a night scene, so it is barely touched. That is the only piece of art
 * direction here, and it lives in STRENGTH below.
 *
 * **In planes.** Every top-level shape in a light picture carries `data-plane="sky"`, `"mid"` or
 * `"fore"`, which says how far away it is. One file per plane is cut from the drawing, each
 * keeping the whole `viewBox` so the three stack back into the original picture exactly. The band
 * then moves them at slightly different rates as the page scrolls, which is what reads as depth.
 * Cutting the planes here rather than drawing them separately is why they cannot drift apart: the
 * source of truth is one drawing, and `--check` fails if a plane file is not what it cuts to.
 *
 * Usage, from `web/`:
 *
 *   node scripts/dark-art.mjs           # write web/public/branches/*-dark.svg and *-<plane>.svg
 *   node scripts/dark-art.mjs --check   # fail if the committed files are out of date
 *
 * `src/content/branch-art.test.ts` runs the same check, so a light picture that changes without
 * its derived files fails the test suite.
 */

import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** Where a night sky starts, and how much room the whole picture gets above it, in OKLCH L. */
const NIGHT_FLOOR = 0.09;
const NIGHT_SPAN = 0.33;

/** Night takes the edge off a colour without draining it. */
const CHROMA_SCALE = 0.78;
const CHROMA_CEILING = 0.085;

/**
 * How much of the transform each drawing gets. 1 is full night, and anything less is art
 * direction. There are two pieces of it, and this is both of them:
 *
 *   - Space Force is already a night scene, so it is barely touched.
 *   - The Navy salute is white smoke against the sky, and the two meet in the night band at full
 *     strength: the puffs come out the same lightness as the sky behind them and disappear. Half
 *     the transform keeps them white enough to see.
 */
const STRENGTH = { "space-force": 0.3, "navy-act": 0.5 };
const FULL_STRENGTH = 1;

/** An act drawing falls back to its scene's strength, so the two stay in the same night. */
export const strengthFor = (name) => STRENGTH[name] ?? STRENGTH[name.replace(/-act$/, "")] ?? FULL_STRENGTH;

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

/* Cutting a drawing into layers
   ----------------------------- */

/** How far away a shape in a scene is. Painted back to front, and the band moves them apart. */
export const PLANES = ["sky", "mid", "fore"];

/**
 * The `<svg>` open tag, its top-level children in source order, and nothing else.
 *
 * Deliberately small: it understands the handful of constructs these drawings use, and throws on
 * anything it does not, because a layer this cannot read is a layer that would silently go
 * missing from the page.
 */
export function topLevel(svg) {
  const opened = /<svg\b[^>]*>/.exec(svg);
  if (!opened) throw new Error("no <svg> element");
  const open = opened[0];
  const end = svg.lastIndexOf("</svg>");
  if (end < 0) throw new Error("no </svg>");

  const inner = svg.slice(open.length + opened.index, end);
  const children = [];
  let at = 0;

  while (at < inner.length) {
    const next = inner.indexOf("<", at);
    if (next < 0) break;
    if (inner.startsWith("<!--", next)) {
      const close = inner.indexOf("-->", next);
      if (close < 0) throw new Error("unterminated comment");
      at = close + 3;
      continue;
    }
    if (inner[next + 1] === "/") throw new Error("a closing tag with nothing open");

    let depth = 0;
    let scan = next;
    for (;;) {
      if (inner.startsWith("<!--", scan)) {
        const close = inner.indexOf("-->", scan);
        if (close < 0) throw new Error("unterminated comment");
        scan = close + 3;
      } else {
        const tag = readTag(inner, scan);
        if (tag.closing) depth -= 1;
        else if (!tag.selfClosing) depth += 1;
        scan = tag.after;
      }
      if (depth <= 0) break;
      const following = inner.indexOf("<", scan);
      if (following < 0) throw new Error("unterminated element");
      scan = following;
    }

    children.push(inner.slice(next, scan));
    at = scan;
  }

  return { open, children };
}

/** One tag, from `<` to the matching `>`, with quoted attribute values skipped over. */
function readTag(text, from) {
  let at = from + 1;
  const closing = text[at] === "/";
  let quote = "";
  while (at < text.length) {
    const char = text[at];
    if (quote) {
      if (char === quote) quote = "";
    } else if (char === '"' || char === "'") quote = char;
    else if (char === ">") {
      return { closing, selfClosing: text[at - 1] === "/", after: at + 1 };
    }
    at += 1;
  }
  throw new Error("unterminated tag");
}

const tagName = (chunk) => /^<\s*([a-z][a-z0-9-]*)/i.exec(chunk)?.[1] ?? "";

/** The value of `data-plane` or `data-actor` on a top-level shape, or null. */
export function layerOf(chunk, attribute) {
  return new RegExp(`\\s${attribute}="([a-z0-9-]+)"`).exec(chunk)?.[1] ?? null;
}

/** A plane file and an actor file are fragments, so they carry no description of their own. */
const asFragment = (open) => open.replace(/\s(?:role|aria-label)="[^"]*"/g, "");

/**
 * One layer of a drawing: the whole `viewBox`, the whole `<defs>`, and only the shapes labelled
 * with this layer's name. The layers of a drawing therefore stack back into it exactly.
 *
 * Throws when a shape carries no label, so a shape added to a drawing cannot quietly fail to
 * appear on the page.
 */
export function layerSvg(svg, attribute, layer) {
  const { open, children } = topLevel(svg);
  const kept = [];
  for (const chunk of children) {
    if (tagName(chunk) === "defs") {
      kept.push(chunk);
      continue;
    }
    const named = layerOf(chunk, attribute);
    if (named === null) throw new Error(`a top-level <${tagName(chunk)}> carries no ${attribute}`);
    if (named === layer) kept.push(chunk);
  }
  if (kept.every((chunk) => tagName(chunk) === "defs")) throw new Error(`nothing is in the ${layer} layer`);
  return `${asFragment(open)}\n${kept.map((chunk) => `  ${chunk}`).join("\n")}\n</svg>\n`;
}

/** Every layer name used in a drawing, in the order the shapes are painted. */
export function layersOf(svg, attribute) {
  const { children } = topLevel(svg);
  const names = [];
  for (const chunk of children) {
    if (tagName(chunk) === "defs") continue;
    const named = layerOf(chunk, attribute);
    if (named === null) throw new Error(`a top-level <${tagName(chunk)}> carries no ${attribute}`);
    if (!names.includes(named)) names.push(named);
  }
  return names;
}

/* The files
   --------- */

const here = dirname(fileURLToPath(import.meta.url));
/** The drawings, by hand. Two per branch: the resting scene, and the actors its vignette moves. */
export const BRANCH_DIR = join(here, "..", "public", "branches");
/** Everything this script writes. Nothing in here is edited by hand. */
export const DERIVED_DIR = join(BRANCH_DIR, "derived");

const ACT = /-act\.svg$/;

/** The scene drawings, by file name, in a stable order. One per branch. */
export async function lightPictures() {
  const files = await readdir(BRANCH_DIR);
  return files.filter((file) => file.endsWith(".svg") && !ACT.test(file)).sort();
}

/** The actor drawings, by file name, in a stable order. One per branch. */
export async function actPictures() {
  const files = await readdir(BRANCH_DIR);
  return files.filter((file) => ACT.test(file)).sort();
}

/**
 * Every file under `derived/`, keyed by name: for each scene, its dark twin and its three planes
 * in both themes; for each actor drawing, one file per actor in both themes.
 */
export async function expectedArt() {
  const art = new Map();
  const add = (file, contents) => art.set(file, contents);

  for (const file of await lightPictures()) {
    const name = file.replace(/\.svg$/, "");
    const strength = strengthFor(name);
    const light = await readFile(join(BRANCH_DIR, file), "utf8");

    add(darkName(file), darkenSvg(light, strength));
    for (const plane of PLANES) {
      const cut = layerSvg(light, "data-plane", plane);
      add(`${name}-${plane}.svg`, cut);
      add(darkName(`${name}-${plane}.svg`), darkenSvg(cut, strength));
    }
  }

  for (const file of await actPictures()) {
    const name = file.replace(/\.svg$/, "");
    const strength = strengthFor(name);
    const light = await readFile(join(BRANCH_DIR, file), "utf8");

    for (const actor of layersOf(light, "data-actor")) {
      const cut = layerSvg(light, "data-actor", actor);
      add(`${name}-${actor}.svg`, cut);
      add(darkName(`${name}-${actor}.svg`), darkenSvg(cut, strength));
    }
  }

  return art;
}

/** Files under `derived/` that nothing derives any more. A renamed drawing leaves these behind. */
export async function orphans(expected) {
  const files = await readdir(DERIVED_DIR).catch(() => []);
  return files.filter((file) => !expected.has(file)).sort();
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const expected = await expectedArt();
  const checking = process.argv.includes("--check");
  const stale = [];

  await mkdir(DERIVED_DIR, { recursive: true });
  for (const [file, contents] of expected) {
    const path = join(DERIVED_DIR, file);
    if (checking) {
      const onDisk = await readFile(path, "utf8").catch(() => "");
      if (onDisk !== contents) stale.push(file);
    } else {
      await writeFile(path, contents);
    }
  }

  const left = await orphans(expected);
  if (!checking) {
    for (const file of left) await rm(join(DERIVED_DIR, file));
    console.log(`wrote ${expected.size} files to ${DERIVED_DIR}`);
    if (left.length > 0) console.log(`removed ${left.length} no longer derived`);
  }

  if (stale.length > 0) console.error(`out of date: ${stale.join(", ")}`);
  if (left.length > 0 && checking) console.error(`no longer derived: ${left.join(", ")}`);
  if (checking && (stale.length > 0 || left.length > 0)) {
    console.error("Run: node scripts/dark-art.mjs");
    process.exit(1);
  }
  if (checking) console.log(`${expected.size} derived pictures are up to date`);
}
