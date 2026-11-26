/**
 * The six vignettes: what happens when a reader presses a branch picture.
 *
 * Each one is a short, calm scene, played once on a press and never on its own. The art is in
 * `public/branches/<branch>-act.svg`, where every actor carries a `data-actor` label and is drawn
 * **where it settles**. This file says only when each actor arrives, where it comes in from, and
 * where it goes as it leaves. Two things follow from drawing the settled position:
 *
 *   - Reduced motion needs no second composition. The actors appear exactly where they are drawn,
 *     with no transform at all, which is the calm "after" frame.
 *   - A timing change never moves the art, and an art change never needs a timing change.
 *
 * Nothing here is violent. No vignette draws a weapon, a round, a flame, an explosion, a target
 * or a casualty, and none shows a seal, emblem, logo, insignia, unit marking or real person.
 * `vignettes.test.ts` holds that line where it can be held by a test.
 */

import type { BranchName } from "./branches";

/** A transform offset from where an actor is drawn. Percentages are of the picture's own size. */
export interface Offset {
  readonly x?: number | string;
  readonly y?: number | string;
  readonly scale?: number;
  readonly rotate?: number;
}

/** One actor's part in a vignette. Seconds throughout. */
export interface Beat {
  /** The `data-actor` label in the branch's act drawing. */
  readonly actor: string;
  /**
   * Where in the frame the actor turns or grows about, as a `transform-origin`. Read off the
   * drawing: a puff swells where it leaves the gun, a ramp swings on its hinge, the beam turns at
   * the satellite. Left out, the actor turns about the middle of the frame, which is right only
   * for something that fills it.
   */
  readonly origin?: string;
  /** Where it comes in from. */
  readonly from: Offset;
  /** Where it goes as it fades out. Every actor leaves: the band returns to its resting picture. */
  readonly out: Offset;
  readonly delay: number;
  /** How long it takes to reach where it is drawn. */
  readonly travel: number;
  /** How long it stays there before it leaves. */
  readonly hold: number;
}

/** How long every actor takes to fade out once it has held. One value, so the scene ends together. */
export const LEAVE = 0.45;

export interface Vignette {
  /** What the reader sees, for `web/TESTING.md` and for the report of what was built. */
  readonly scene: string;
  readonly beats: readonly Beat[];
}

/** A puff of smoke rising from the saluting gun. Three of them, one after another. */
const puff = (actor: string, origin: string, delay: number): Beat => ({
  actor,
  origin,
  from: { x: 9, y: 13, scale: 0.5 },
  out: { x: -8, y: -14, scale: 1.3 },
  delay,
  travel: 0.55,
  hold: 0.85,
});

/** Someone stepping down or across. Drawn where they end up, so they walk into place. */
const walker = (actor: string, origin: string, from: Offset, out: Offset, delay: number, travel = 0.5): Beat => ({
  actor,
  origin,
  from: { scale: 0.92, ...from },
  out,
  delay,
  travel,
  hold: 0.6,
});

/** A status marker settling onto the map. */
const ping = (actor: string, origin: string, delay: number): Beat => ({
  actor,
  origin,
  from: { scale: 0.3 },
  out: { scale: 1.4 },
  delay,
  travel: 0.4,
  hold: 0.9,
});

export const VIGNETTES: Record<BranchName, Vignette> = {
  Navy: {
    scene:
      "a ceremonial gun salute: a pennant breaks out at the mast and three puffs of white smoke rise out to open sea",
    beats: [
      { actor: "pennant", origin: "44% 44%", from: { rotate: -16 }, out: { rotate: -9 }, delay: 0.1, travel: 0.45, hold: 1.5 },
      puff("puff-a", "31% 53%", 0.35),
      puff("puff-b", "26% 47%", 0.7),
      puff("puff-c", "21% 40%", 1.05),
    ],
  },
  "Coast Guard": {
    scene: "a boarding: the small boat comes alongside the cutter and two crew step across to the after deck",
    beats: [
      { actor: "boat", from: { x: 58 }, out: { x: 13 }, delay: 0, travel: 1, hold: 1.3 },
      walker("crew-a", "66% 58%", { x: 25, y: 7 }, { y: -4 }, 0.95, 0.55),
      walker("crew-b", "69% 59%", { x: 25, y: 7 }, { y: -4 }, 1.2, 0.55),
    ],
  },
  "Marine Corps": {
    scene: "a dismount: three Marines come down the ramp and walk up the sand",
    beats: [
      walker("march-a", "18% 85%", { x: 33, y: -15 }, { x: -17, y: 5 }, 0, 0.8),
      walker("march-b", "12% 88%", { x: 36, y: -17 }, { x: -19, y: 6 }, 0.35, 0.85),
      walker("march-c", "5% 91%", { x: 39, y: -19 }, { x: -21, y: 7 }, 0.7, 0.9),
    ],
  },
  Army: {
    scene: "a dismount: a tracked carrier pulls up to the right of the truck, and three soldiers step down behind it",
    beats: [
      // In from off the right edge, and out the same way. It is parked clear of the truck, so the
      // two vehicles are never on top of one another at any point in the scene.
      { actor: "ifv", from: { x: 92 }, out: { x: 22 }, delay: 0, travel: 1.1, hold: 1.4 },
      walker("troop-a", "90% 87%", { x: 0, y: -10 }, { x: -9, y: 4 }, 1.35, 0.45),
      walker("troop-b", "85% 88%", { x: 20, y: -18 }, { x: -11, y: 5 }, 1.55, 0.5),
      walker("troop-c", "80% 90%", { x: 44, y: -26 }, { x: -13, y: 6 }, 1.75, 0.55),
    ],
  },
  "Air Force": {
    scene: "a flyover: three swept-wing silhouettes cross the frame in formation, trailing contrails",
    beats: [{ actor: "flight", from: { x: "-58%" }, out: { x: "58%" }, delay: 0, travel: 1.5, hold: 0.45 }],
  },
  "Space Force": {
    scene: "monitoring: a map grid comes up, a soft beam sweeps across it, and three status markers settle into view",
    beats: [
      { actor: "grid", from: { scale: 0.98 }, out: { scale: 1.02 }, delay: 0, travel: 0.5, hold: 1.9 },
      { actor: "beam", origin: "73% 39%", from: { rotate: -26 }, out: { rotate: 26 }, delay: 0.3, travel: 1.05, hold: 0.3 },
      ping("ping-a", "43% 73%", 0.9),
      ping("ping-b", "60% 81%", 1.15),
      ping("ping-c", "33% 88%", 1.4),
    ],
  },
};

/** How long a vignette runs, in seconds: the last actor's exit. */
export function lengthOf(vignette: Vignette): number {
  return Math.max(...vignette.beats.map((beat) => beat.delay + beat.travel + beat.hold + LEAVE));
}
