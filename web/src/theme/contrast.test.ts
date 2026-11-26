import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MODES, PAIRS, measure, readDeclarations, resolve } from "./contrast";

/**
 * The palette's own test. It reads the shipped token file, so editing a stop in `theme.css`
 * either keeps the page readable or fails here.
 */

const webFile = (path: string) => fileURLToPath(new URL(`../../${path}`, import.meta.url));

const THEME_CSS = readFileSync(webFile("src/app/theme.css"), "utf8");
const GLOBALS_CSS = readFileSync(webFile("src/app/globals.css"), "utf8");
const declarations = readDeclarations(THEME_CSS);

/**
 * Semantic tokens that are never drawn over another token in this list: a hairline between two
 * rows of text, a hover colour measured through the pair it replaces, or the edge of a panel that
 * already carries a 3:1 rule of its own. WCAG 1.4.11 asks 3:1 of the boundary of a control and of
 * a graphic you have to make out, not of every line on the page.
 */
const NOT_A_PAIR = new Set([
  "--color-border",
  "--color-link-hover",
  "--color-primary-tint",
  "--color-surface",
  "--color-surface-raised",
  "--color-surface-sunken",
  "--color-bg",
  "--color-chip-bg",
  "--color-danger-bg",
  "--color-danger-border",
  "--color-warning-bg",
  "--color-warning-border",
]);

describe("the palette", () => {
  it("resolves every token in both themes", () => {
    const tokens = [...declarations.keys()].filter((name) => name.startsWith("--color-"));
    expect(tokens.length).toBeGreaterThan(20);
    for (const token of tokens) {
      for (const mode of MODES) {
        expect(resolve(declarations, token, mode), `${token} in ${mode}`).toMatch(/^#[0-9a-f]{6}$/);
      }
    }
  });

  it.each(measure(declarations))(
    "$use, $mode: $foregroundValue on $backgroundValue",
    ({ ratio, minimum, mode, use }) => {
      expect(ratio, `${use} in ${mode} mode needs ${minimum}:1`).toBeGreaterThanOrEqual(minimum);
    },
  );

  it("measures every semantic colour that something is drawn on top of", () => {
    const measured = new Set(PAIRS.flatMap((pair) => [pair.foreground, pair.background]));
    const unmeasured = [...declarations.keys()].filter(
      (name) => name.startsWith("--color-") && !measured.has(name) && !NOT_A_PAIR.has(name),
    );
    expect(unmeasured, "add these to PAIRS in contrast.ts, or to NOT_A_PAIR with a reason").toEqual([]);
  });

  it("keeps every colour in the token file, so the two themes cannot drift apart", () => {
    const loose = [...GLOBALS_CSS.matchAll(/#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|color-mix)\(/gi)];
    expect(loose.map((match) => match[0]), "use a --color-* token from theme.css instead").toEqual([]);
  });

  it("is written down with the numbers it actually measures", () => {
    const doc = readFileSync(webFile("docs/palette.md"), "utf8");
    const light = measure(declarations).filter((row) => row.mode === "light");
    const dark = measure(declarations).filter((row) => row.mode === "dark");

    for (const [index, row] of light.entries()) {
      const written = `| ${row.use} | ${row.ratio.toFixed(2)}:1 | ${dark[index]?.ratio.toFixed(2)}:1 | ${row.minimum.toFixed(1)}:1 |`;
      expect(doc, "docs/palette.md is out of date").toContain(written);
    }
    for (const token of declarations.keys()) {
      if (!token.startsWith("--color-")) continue;
      const written = `| \`${token}\` | \`${resolve(declarations, token, "light")}\` | \`${resolve(declarations, token, "dark")}\` |`;
      expect(doc, "docs/palette.md is out of date").toContain(written);
    }
  });

  it("declares both themes on one line per token, so neither can be forgotten", () => {
    for (const [name, value] of declarations) {
      if (!name.startsWith("--color-")) continue;
      expect(value, name).toMatch(/^light-dark\(/);
    }
  });
});
