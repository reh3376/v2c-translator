import { describe, expect, it } from "vitest";
import { PLANES } from "@/content/branches";
import { LEAVE, lengthOf, VIGNETTES } from "@/content/vignettes";
import {
  arrive,
  cellWindow,
  disclose,
  DURATION,
  enter,
  fan,
  item,
  lift,
  PARALLAX,
  PLANE_BLEED,
  pressable,
  stagger,
  staggerInView,
  sweep,
  travelOf,
  vignette,
} from "./motion";

/** Everything the page can animate, built both ways. */
const bundles = (reduced: boolean) => ({
  enter: enter(reduced),
  "enter, delayed": enter(reduced, 0.1),
  stagger: stagger(reduced),
  item: item(reduced),
  lift: lift(reduced),
  pressable: pressable(reduced),
  disclose: disclose(reduced),
});

/** Anything that moves a thing or changes its size. Opacity is not movement. */
const MOVES = ["x", "y", "scale", "height", "rotate"];

function keysOf(value: unknown, into: string[] = []): string[] {
  if (Array.isArray(value)) value.forEach((entry) => keysOf(entry, into));
  else if (value && typeof value === "object") {
    for (const [key, nested] of Object.entries(value)) {
      into.push(key);
      keysOf(nested, into);
    }
  }
  return into;
}

function durationsOf(value: unknown, into: number[] = []): number[] {
  if (Array.isArray(value)) value.forEach((entry) => durationsOf(entry, into));
  else if (value && typeof value === "object") {
    for (const [key, nested] of Object.entries(value)) {
      if (key === "duration" && typeof nested === "number") into.push(nested);
      else durationsOf(nested, into);
    }
  }
  return into;
}

describe("when the reader asks for less motion", () => {
  it("animates nothing that moves", () => {
    for (const [name, props] of Object.entries(bundles(true))) {
      expect(keysOf(props).filter((key) => MOVES.includes(key)), name).toEqual([]);
    }
  });

  it("takes no time", () => {
    for (const [name, props] of Object.entries(bundles(true))) {
      for (const duration of durationsOf(props)) expect(duration, name).toBe(0);
    }
  });

  it("drops hover and press feedback, so pictures and buttons stay still", () => {
    expect(lift(true)).toEqual({});
    expect(pressable(true)).toEqual({});
  });

  it("stops the progress bar sweeping, leaving the caller to show a still bar", () => {
    expect(sweep(true)).toBeNull();
  });

  it("still fades things in, because opacity is not movement", () => {
    expect(enter(true).initial).toEqual({ opacity: 0 });
    expect(enter(true).animate).toEqual({ opacity: 1 });
  });
});

describe("when motion is allowed", () => {
  it("keeps every entrance and every piece of feedback between 150 and 300 ms", () => {
    for (const [name, props] of Object.entries(bundles(false))) {
      for (const duration of durationsOf(props)) {
        if (duration === 0) continue; // a stagger container times its children, not itself
        expect(duration, name).toBeGreaterThanOrEqual(0.12);
        expect(duration, name).toBeLessThanOrEqual(0.3);
      }
    }
  });

  it("moves only along y, scale and a disclosure's height", () => {
    const moved = new Set(keysOf(bundles(false)).filter((key) => MOVES.includes(key)));
    expect([...moved].sort()).toEqual(["height", "scale", "y"]);
  });

  it("sweeps the progress bar slowly enough to read as waiting, and repeats", () => {
    const slide = sweep(false);
    expect(slide?.transition.duration).toBe(DURATION.progressSweep);
    expect(DURATION.progressSweep).toBeGreaterThan(1);
    expect(slide?.transition.repeat).toBe(Infinity);
  });

  it("gives a picture hover feedback but no press state, because it is not a control", () => {
    expect(lift(false).whileHover).toBeDefined();
    expect(lift(false).whileTap).toBeUndefined();
    expect(pressable(false).whileTap).toBeDefined();
  });
});

/* The scroll-driven parts: the layered hero, the story, and the vignettes.
   These are kept apart from the bundles above because two of their rules differ. A vignette is
   something the reader asked for by pressing a picture, so it runs for seconds rather than
   milliseconds; and `fan` carries a resting position in `style`, which is where a document sits
   rather than something it does. */

const MOVED = (props: unknown) => keysOf(props).filter((key) => MOVES.includes(key));

describe("the planes of a branch picture", () => {
  it("move at a different rate each, so the eye reads the difference as distance", () => {
    const scrolls = PLANES.map((plane) => PARALLAX[plane].scroll);
    expect(new Set(scrolls).size).toBe(PLANES.length);
    expect(PARALLAX.sky.scroll).toBeGreaterThan(0);
    expect(PARALLAX.fore.scroll).toBeLessThan(0);
  });

  it("lean further under the pointer the nearer they are", () => {
    expect(PARALLAX.sky.pointer).toBeLessThan(PARALLAX.mid.pointer);
    expect(PARALLAX.mid.pointer).toBeLessThan(PARALLAX.fore.pointer);
  });

  it("never travel further than the bleed, so no plane can expose the one behind it", () => {
    for (const plane of PLANES) expect(travelOf(plane), plane).toBeLessThanOrEqual(PLANE_BLEED);
  });

  it("stay subtle: past a couple of dozen pixels this reads as shapes sliding, not as depth", () => {
    for (const plane of PLANES) expect(Math.abs(PARALLAX[plane].scroll), plane).toBeLessThanOrEqual(24);
  });
});

describe("the blocks of the form in the second step", () => {
  it("light one after another, in order", () => {
    const starts = Array.from({ length: 24 }, (_, i) => cellWindow(i, 24)[0]);
    expect([...starts].sort((a, b) => a - b)).toEqual(starts);
  });

  it("are all lit before the step leaves the window, so nobody scrolls past a half-read form", () => {
    expect(cellWindow(23, 24)[1]).toBeLessThan(1);
    expect(cellWindow(0, 24)[0]).toBeGreaterThan(0);
  });
});

describe("a section that arrives as it is scrolled to", () => {
  it("animates nothing at all before the page has mounted, so no JavaScript means no hiding", () => {
    expect(arrive(false, false)).toEqual({});
    expect(arrive(false, true)).toEqual({});
    expect(staggerInView(false, false)).toEqual({});
    expect(fan(false, false, 0).initial).toBeUndefined();
  });

  it("arrives once, not every time it is scrolled past", () => {
    expect(arrive(true, false).viewport?.once).toBe(true);
    expect(staggerInView(true, false).viewport?.once).toBe(true);
  });

  it("does not run at all when the reader asks for less motion, so nothing waits to be scrolled to", () => {
    expect(arrive(true, true)).toEqual({});
    expect(staggerInView(true, true)).toEqual({});
    expect(fan(true, true, 0).initial).toBeUndefined();
  });

  it("is quick, and never slower than any other entrance on the page", () => {
    for (const duration of durationsOf(arrive(true, false))) expect(duration).toBeLessThanOrEqual(0.3);
  });
});

describe("the documents fanning out of the stack", () => {
  it("end up fanned however they got there, so the stack reads as three documents either way", () => {
    for (const index of [0, 1, 2]) {
      const settled = fan(true, false, index).whileInView;
      const still = fan(true, true, index).style;
      expect(still, `${index}`).toBeDefined();
      expect({ rotate: settled?.rotate, x: settled?.x }, `${index}`).toEqual(still);
      expect(fan(false, false, index).style, `${index}`).toEqual(still);
    }
  });

  it("turns only when motion is allowed", () => {
    expect(MOVED({ whileInView: fan(true, false, 0).whileInView })).toEqual(["rotate", "x"]);
  });
});

describe("a vignette", () => {
  const beats = Object.values(VIGNETTES).flatMap((scene) => scene.beats);

  it("brings every actor back to where it is drawn, and then takes it away", () => {
    for (const beat of beats) {
      const played = vignette(false, beat);
      const opacity = played.animate.opacity as number[];
      expect(opacity, beat.actor).toEqual([0, 1, 1, 0]);
      for (const [key, frames] of Object.entries(played.animate)) {
        if (key === "opacity") continue;
        const [, settled, held] = frames as (number | string)[];
        expect(settled, `${beat.actor} ${key}`).toBe(held);
        expect(settled, `${beat.actor} ${key}`).toBe(key === "scale" ? 1 : typeof settled === "string" ? "0%" : 0);
      }
    }
  });

  it("holds a keyframe at the moment the actor settles and at the moment it leaves", () => {
    for (const beat of beats) {
      const { duration, times } = vignette(false, beat).transition as { duration: number; times: [number, number, number, number] };
      expect(duration, beat.actor).toBeCloseTo(beat.travel + beat.hold + LEAVE, 5);
      expect(times[1] * duration, beat.actor).toBeCloseTo(beat.travel, 5);
      expect(times[2] * duration, beat.actor).toBeCloseTo(beat.travel + beat.hold, 5);
    }
  });

  it("moves nothing when the reader asks for less motion: the actor fades up where it is drawn", () => {
    for (const beat of beats) expect(MOVED(vignette(true, beat)), beat.actor).toEqual([]);
  });

  it("crosses in and out in a fifth of a second when motion is reduced", () => {
    for (const beat of beats) {
      const { duration, times } = vignette(true, beat).transition as { duration: number; times: [number, number, number, number] };
      expect(times[1] * duration, beat.actor).toBeCloseTo(DURATION.crossFade, 5);
      expect(duration - times[2] * duration, beat.actor).toBeCloseTo(DURATION.crossFade, 5);
    }
  });

  it("is over in a few seconds, because it is a scene and not a film", () => {
    for (const [branch, scene] of Object.entries(VIGNETTES)) {
      expect(lengthOf(scene), branch).toBeGreaterThan(2);
      expect(lengthOf(scene), branch).toBeLessThanOrEqual(4);
    }
  });

  it("never repeats, so nothing on this page can loop on its own", () => {
    for (const beat of beats) {
      expect(vignette(false, beat).transition, beat.actor).not.toHaveProperty("repeat");
      expect(vignette(true, beat).transition, beat.actor).not.toHaveProperty("repeat");
    }
  });
});
