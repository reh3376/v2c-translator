/**
 * The six branches the translator reports, with one bundled picture each.
 *
 * `name` is spelled exactly as in `BRANCHES` in `src/dd214kw/parse.py`, because the report's
 * `profile.context.branch` carries those strings and the page matches on them. `branches.test.ts`
 * reads that table and fails when the two drift apart.
 *
 * Each illustration has a dark twin, generated from it by `scripts/dark-art.mjs`.
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
  /** Path under `web/public/`. Used when `photo` is absent. */
  readonly illustration: string;
  /**
   * The same drawing after dark, written by `scripts/dark-art.mjs` from the light one. Both are
   * in the markup and the stylesheet shows one, so switching theme swaps no image at runtime.
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
    illustrationDark: "/branches/navy-dark.svg",
    alt: "A warship on open water at first light, drawn as a flat silhouette.",
  },
  {
    name: "Coast Guard",
    setting: "In the surf",
    illustration: "/branches/coast-guard.svg",
    illustrationDark: "/branches/coast-guard-dark.svg",
    alt: "A patrol cutter with a boat on davits running through surf past a rocky point, drawn as a flat silhouette.",
  },
  {
    name: "Marine Corps",
    setting: "Across the beach",
    illustration: "/branches/marine-corps.svg",
    illustrationDark: "/branches/marine-corps-dark.svg",
    alt: "A landing craft at the surf line with its bow ramp down on the sand, drawn as a flat silhouette.",
  },
  {
    name: "Army",
    setting: "On the ground",
    illustration: "/branches/army.svg",
    illustrationDark: "/branches/army-dark.svg",
    alt: "A utility vehicle on a dirt track below a ridge line, drawn as a flat silhouette.",
  },
  {
    name: "Air Force",
    setting: "In the air",
    illustration: "/branches/air-force.svg",
    illustrationDark: "/branches/air-force-dark.svg",
    alt: "Two swept-wing aircraft above a cloud deck, drawn as flat silhouettes with no markings.",
  },
  {
    name: "Space Force",
    setting: "In orbit",
    illustration: "/branches/space-force.svg",
    illustrationDark: "/branches/space-force-dark.svg",
    alt: "A satellite in orbit above the curve of the earth, drawn as a flat illustration.",
  },
];

/** The panel for a branch as the report spells it, or undefined when no document stated one. */
export function panelFor(branch: string | null | undefined): BranchPanel | undefined {
  return BRANCH_PANELS.find((panel) => panel.name === branch);
}
