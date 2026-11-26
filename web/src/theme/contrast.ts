/**
 * The contrast arithmetic, and the list of colour pairs this page actually puts on screen.
 *
 * `src/theme/contrast.test.ts` asserts every pair here against WCAG AA in both themes, and
 * `scripts/palette-table.mjs` prints the same numbers for `web/docs/palette.md`. Both read
 * `src/app/theme.css`, so the ratios are measured from the shipped tokens rather than copied
 * from a design file.
 */

/** sRGB, 0-255 per channel. */
export interface Rgb {
  readonly r: number;
  readonly g: number;
  readonly b: number;
}

/** The two themes a token declares a value for. */
export type Mode = "light" | "dark";

export const MODES: readonly Mode[] = ["light", "dark"];

/**
 * What the pair is: `body` for text under 24 px (or under 19 px bold), `large` for text above
 * that, `ui` for the edge of a control or a focus ring. WCAG AA asks 4.5:1 of the first and
 * 3:1 of the other two.
 */
export type PairKind = "body" | "large" | "ui";

export const MINIMUM: Record<PairKind, number> = { body: 4.5, large: 3, ui: 3 };

export function parseHex(value: string): Rgb {
  const match = /^#([0-9a-f]{6})$/i.exec(value.trim());
  if (!match?.[1]) throw new Error(`not a six-digit hexadecimal colour: ${value}`);
  const n = Number.parseInt(match[1], 16);
  return { r: (n >> 16) & 0xff, g: (n >> 8) & 0xff, b: n & 0xff };
}

/** WCAG 2.1 relative luminance. */
export function relativeLuminance({ r, g, b }: Rgb): number {
  const channel = (value: number) => {
    const s = value / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG 2.1 contrast ratio, 1 to 21. Order of the two colours does not matter. */
export function contrastRatio(a: string, b: string): number {
  const first = relativeLuminance(parseHex(a));
  const second = relativeLuminance(parseHex(b));
  const [high, low] = first >= second ? [first, second] : [second, first];
  return (high + 0.05) / (low + 0.05);
}

/** Rounded the way the pass/fail line is read: 4.49 is not 4.5. */
export const round = (ratio: number) => Math.floor(ratio * 100) / 100;

/**
 * Every declaration in the token file, by name, in source order.
 *
 * Deliberately small: it understands a six-digit hexadecimal colour, `var(--other)`, and
 * `light-dark(a, b)`, and throws on anything else. A token written in a form this cannot read is
 * a token the contrast test cannot check, so failing loudly is the point.
 */
export function readDeclarations(css: string): Map<string, string> {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const declarations = new Map<string, string>();
  for (const [, name, value] of withoutComments.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;}]+)[;}]/gi)) {
    if (name && value) declarations.set(name, value.trim());
  }
  return declarations;
}

const LIGHT_DARK = /^light-dark\(\s*(.+?)\s*,\s*(.+?)\s*\)$/i;
const VAR = /^var\(\s*(--[a-z0-9-]+)\s*\)$/i;

/** The hexadecimal value a token resolves to in one theme. */
export function resolve(declarations: Map<string, string>, token: string, mode: Mode, depth = 0): string {
  if (depth > 8) throw new Error(`${token} resolves through too many references`);
  const value = declarations.get(token);
  if (value === undefined) throw new Error(`no such token: ${token}`);

  const pair = LIGHT_DARK.exec(value);
  if (pair) {
    const side = mode === "light" ? pair[1] : pair[2];
    return resolveValue(declarations, side ?? "", mode, token, depth);
  }
  return resolveValue(declarations, value, mode, token, depth);
}

function resolveValue(
  declarations: Map<string, string>,
  value: string,
  mode: Mode,
  token: string,
  depth: number,
): string {
  const reference = VAR.exec(value);
  if (reference?.[1]) return resolve(declarations, reference[1], mode, depth + 1);
  if (/^#[0-9a-f]{6}$/i.test(value)) return value.toLowerCase();
  throw new Error(`${token} is ${value}, which contrast.ts cannot read in ${mode} mode`);
}

/** A pair of tokens the page shows together, and the rule it has to meet. */
export interface Pair {
  /** What the reader is looking at. Used as the row label in `web/docs/palette.md`. */
  readonly use: string;
  readonly foreground: string;
  readonly background: string;
  readonly kind: PairKind;
}

/**
 * The pairs the page puts on screen. Each one was read off the stylesheet, not imagined: if a
 * rule in `globals.css` sets a colour on a background, the pair belongs here.
 */
export const PAIRS: readonly Pair[] = [
  { use: "Body text on the page", foreground: "--color-text", background: "--color-bg", kind: "body" },
  { use: "Body text on a surface", foreground: "--color-text", background: "--color-surface", kind: "body" },
  {
    use: "Body text on a raised surface",
    foreground: "--color-text",
    background: "--color-surface-raised",
    kind: "body",
  },
  {
    use: "The entry copied off the document",
    foreground: "--color-text",
    background: "--color-surface-sunken",
    kind: "body",
  },
  {
    use: "Secondary text on the page",
    foreground: "--color-text-secondary",
    background: "--color-bg",
    kind: "body",
  },
  {
    use: "Secondary text on a surface",
    foreground: "--color-text-secondary",
    background: "--color-surface",
    kind: "body",
  },
  { use: "Captions on the page", foreground: "--color-text-muted", background: "--color-bg", kind: "body" },
  {
    use: "Captions on a surface",
    foreground: "--color-text-muted",
    background: "--color-surface",
    kind: "body",
  },
  { use: "Primary button label", foreground: "--color-on-primary", background: "--color-primary", kind: "body" },
  {
    use: "Primary button label, hovered",
    foreground: "--color-on-primary",
    background: "--color-primary-hover",
    kind: "body",
  },
  {
    use: "Secondary button label",
    foreground: "--color-primary-text",
    background: "--color-surface",
    kind: "body",
  },
  {
    use: "Quiet button label on the page",
    foreground: "--color-primary-text",
    background: "--color-bg",
    kind: "body",
  },
  {
    use: "Secondary button label, hovered",
    foreground: "--color-primary-text",
    background: "--color-primary-tint",
    kind: "body",
  },
  { use: "A link on the page", foreground: "--color-link", background: "--color-bg", kind: "body" },
  { use: "A link on a surface", foreground: "--color-link", background: "--color-surface", kind: "body" },
  { use: "A keyword chip", foreground: "--color-chip-text", background: "--color-chip-bg", kind: "body" },
  {
    use: "The branch the documents named",
    foreground: "--color-chip-text",
    background: "--color-chip-bg",
    kind: "body",
  },
  { use: "A file that could not be read", foreground: "--color-danger-text", background: "--color-danger-bg", kind: "body" },
  {
    use: "A note from the translator",
    foreground: "--color-warning-text",
    background: "--color-warning-bg",
    kind: "body",
  },
  { use: "A copy that worked", foreground: "--color-success-text", background: "--color-bg", kind: "body" },
  { use: "The wordmark", foreground: "--color-primary", background: "--color-bg", kind: "large" },
  { use: "The focus ring on the page", foreground: "--color-focus", background: "--color-bg", kind: "ui" },
  { use: "The focus ring on a surface", foreground: "--color-focus", background: "--color-surface", kind: "ui" },
  {
    use: "The edge of the drop zone",
    foreground: "--color-border-strong",
    background: "--color-surface",
    kind: "ui",
  },
  {
    use: "A section rule on the page",
    foreground: "--color-border-strong",
    background: "--color-bg",
    kind: "ui",
  },
  { use: "The primary button against the page", foreground: "--color-primary", background: "--color-bg", kind: "ui" },
  {
    use: "The rule beside a file that could not be read",
    foreground: "--color-danger-rule",
    background: "--color-danger-bg",
    kind: "ui",
  },
  { use: "The accent rule", foreground: "--color-accent", background: "--color-bg", kind: "ui" },
  { use: "The accent rule on a surface", foreground: "--color-accent", background: "--color-surface", kind: "ui" },
];

export interface Measurement extends Pair {
  readonly mode: Mode;
  readonly foregroundValue: string;
  readonly backgroundValue: string;
  readonly ratio: number;
  readonly minimum: number;
  readonly passes: boolean;
}

/** Every pair, measured in both themes. */
export function measure(declarations: Map<string, string>, pairs: readonly Pair[] = PAIRS): Measurement[] {
  return MODES.flatMap((mode) =>
    pairs.map((pair) => {
      const foregroundValue = resolve(declarations, pair.foreground, mode);
      const backgroundValue = resolve(declarations, pair.background, mode);
      const ratio = round(contrastRatio(foregroundValue, backgroundValue));
      const minimum = MINIMUM[pair.kind];
      return { ...pair, mode, foregroundValue, backgroundValue, ratio, minimum, passes: ratio >= minimum };
    }),
  );
}
