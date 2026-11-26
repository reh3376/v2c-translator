/**
 * The six branches the translator reports, with one bundled picture each.
 *
 * `name` is spelled exactly as in `BRANCHES` in `src/dd214kw/parse.py`, because the report's
 * `profile.context.branch` carries those strings and the page matches on them. `branches.test.ts`
 * reads that table and fails when the two drift apart.
 *
 * Every file the page actually shows is generated from these drawings by `scripts/dark-art.mjs`,
 * into `public/branches/derived/`: a dark twin of each, the three depth planes the band moves
 * apart as the page scrolls, and one file per actor in the branch's vignette. Nothing under
 * `derived/` is edited by hand, and `pnpm dark-art --check` fails when it is stale.
 *
 * The pictures are original illustrations, drawn for this page. No service seal, emblem, logo or
 * insignia appears in any of them, and none is implied: the page is not endorsed by the Department
 * of Defense or any service, and the footer says so. They share one horizon, so the row reads left
 * to right as a single scene from sea level to orbit.
 *
 * To use a public-domain photograph instead, see "Swapping in a photograph" in `web/TESTING.md`.
 * The type makes the credit line mandatory, because a credited source is the condition for using
 * public-domain DoD or DVIDS photography.
 */

export const BRANCH_NAMES = ["Navy", "Coast Guard", "Marine Corps", "Army", "Air Force", "Space Force"] as const;

export type BranchName = (typeof BRANCH_NAMES)[number];

/** A photograph and the credit line shown under it. Neither is useful without the other. */
export interface Photograph {
  /** Path under `web/public/`, served from this computer. */
  readonly src: string;
  /** Shown to the reader, e.g. "U.S. Navy photo by Mass Communication Specialist 2nd Class A. Example". */
  readonly credit: string;
}

export interface BranchPanel {
  readonly name: BranchName;
  /** Where the picture is set. The row is ordered by these, from sea level to orbit. */
  readonly setting: string;
  /** Path under `web/public/`. The drawing the planes are cut from, and the photograph's stand-in. */
  readonly illustration: string;
  /**
   * The same drawing after dark, written by `scripts/dark-art.mjs` from the light one. Both the
   * day and the night file are in the markup and the stylesheet shows one, so switching theme
   * swaps no image at runtime.
   */
  readonly illustrationDark: string;
  readonly alt: string;
  /** A credited public-domain photograph, when one has been added. It replaces the illustration. */
  readonly photo?: Photograph;
}

export const BRANCH_PANELS: readonly BranchPanel[] = [
  {
    name: "Navy",
    setting: "At sea",
    illustration: "/branches/navy.svg",
    illustrationDark: "/branches/derived/navy-dark.svg",
    alt: "A warship on open water at first light, drawn as a flat silhouette.",
  },
  {
    name: "Coast Guard",
    setting: "In the surf",
    illustration: "/branches/coast-guard.svg",
    illustrationDark: "/branches/derived/coast-guard-dark.svg",
    alt: "A patrol cutter with a boat on davits running through surf past a rocky point, drawn as a flat silhouette.",
  },
  {
    name: "Marine Corps",
    setting: "Across the beach",
    illustration: "/branches/marine-corps.svg",
    illustrationDark: "/branches/derived/marine-corps-dark.svg",
    alt: "A landing craft at the surf line with its bow ramp down on the sand, drawn as a flat silhouette.",
  },
  {
    name: "Army",
    setting: "On the ground",
    illustration: "/branches/army.svg",
    illustrationDark: "/branches/derived/army-dark.svg",
    alt: "A utility vehicle on a dirt track below a ridge line, drawn as a flat silhouette.",
  },
  {
    name: "Air Force",
    setting: "In the air",
    illustration: "/branches/air-force.svg",
    illustrationDark: "/branches/derived/air-force-dark.svg",
    alt: "Two swept-wing aircraft above a cloud deck, drawn as flat silhouettes with no markings.",
  },
  {
    name: "Space Force",
    setting: "In orbit",
    illustration: "/branches/space-force.svg",
    illustrationDark: "/branches/derived/space-force-dark.svg",
    alt: "A satellite in orbit above the curve of the earth, drawn as a flat illustration.",
  },
];

/** The panel for a branch as the report spells it, or undefined when no document stated one. */
export function panelFor(branch: string | null | undefined): BranchPanel | undefined {
  return BRANCH_PANELS.find((panel) => panel.name === branch);
}

/**
 * How far away a shape in a drawing is, back to front. `scripts/dark-art.mjs` cuts one file per
 * plane, each keeping the whole `viewBox`, so stacking all three paints the original picture and
 * moving them at slightly different rates is what reads as depth.
 */
export const PLANES = ["sky", "mid", "fore"] as const;

export type Plane = (typeof PLANES)[number];

/** A drawing in both themes. Both are in the markup, and the stylesheet shows one. */
export interface Layer {
  readonly day: string;
  readonly night: string;
}

/** The name `scripts/dark-art.mjs` gives a branch's derived files. */
const slug = (panel: BranchPanel) => panel.illustration.replace("/branches/", "").replace(/\.svg$/, "");

const derived = (name: string): Layer => ({
  day: `/branches/derived/${name}.svg`,
  night: `/branches/derived/${name}-dark.svg`,
});

/** One depth plane of a branch's picture. */
export const planeArt = (panel: BranchPanel, plane: Plane): Layer => derived(`${slug(panel)}-${plane}`);

/** One actor in a branch's vignette, drawn where it settles. */
export const actorArt = (panel: BranchPanel, actor: string): Layer => derived(`${slug(panel)}-act-${actor}`);
