import { describe, expect, it } from "vitest";
import { disclose, DURATION, enter, item, lift, pressable, stagger, sweep } from "./motion";

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
