/**
 * The page's whole animation vocabulary, as plain objects spread onto Motion elements.
 *
 * Keeping it here rather than inline means the reduced-motion contract is one testable thing:
 * every bundle built with `reduced === true` animates nothing and takes no time. `MotionConfig
 * reducedMotion="user"` in `calm-motion.tsx` already strips transforms for people who ask the
 * operating system for less motion; these functions make that explicit, and cover the repeating
 * progress animation, which no config can soften.
 *
 * Entrances and feedback last 150-300 ms. The only longer animation is the progress bar, which
 * repeats while the translator works and has to move slowly enough to read as waiting.
 */

import type { Easing, TargetAndTransition, Transition, Variants } from "motion/react";
import type { Plane } from "@/content/branches";
import { LEAVE, type Beat, type Offset } from "@/content/vignettes";

/** Seconds. */
export const DURATION = {
  enter: 0.24,
  disclose: 0.2,
  press: 0.12,
  /** One sweep of the indeterminate progress bar. Repeats, so it is paced, not quick. */
  progressSweep: 1.3,
  /** A vignette fading its actors in and out when the reader has asked for less motion. */
  crossFade: 0.2,
  /** One document turning out of the stack in the first step of "How it works". */
  fan: 0.3,
} as const;

/** A gentle deceleration. Nothing overshoots: this page reports facts about someone's service. */
export const EASE_OUT: Easing = [0.22, 0.61, 0.36, 1];

/**
 * The only values anything here animates: opacity, two transforms, and the height of a
 * disclosure. Nothing else moves, so nothing else can push the text around while it is read.
 */
export interface Entrance {
  readonly initial: TargetAndTransition;
  readonly animate: TargetAndTransition;
  readonly transition: Transition;
}

const STILL: Transition = { duration: 0 };

/** A section fading up as it arrives. */
export function enter(reduced: boolean, delay = 0): Entrance {
  if (reduced) return { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: STILL };
  return {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: DURATION.enter, ease: EASE_OUT, delay },
  };
}

export interface Stagger {
  readonly initial: "hidden";
  readonly animate: "shown";
  readonly variants: Variants;
}

/** A list whose children arrive one just after another. Pair with `item`. */
export function stagger(reduced: boolean, step = 0.018): Stagger {
  const transition: Transition = reduced ? STILL : { duration: 0, staggerChildren: step };
  return { initial: "hidden", animate: "shown", variants: { hidden: {}, shown: { transition } } };
}

export interface Item {
  readonly variants: Variants;
}

/** A child of a `stagger` list: a keyword chip, a resource link, a branch picture. */
export function item(reduced: boolean): Item {
  if (reduced) {
    return { variants: { hidden: { opacity: 0 }, shown: { opacity: 1, transition: STILL } } };
  }
  return {
    variants: {
      hidden: { opacity: 0, y: 6 },
      shown: { opacity: 1, y: 0, transition: { duration: DURATION.enter, ease: EASE_OUT } },
    },
  };
}

export interface Feedback {
  readonly whileHover?: TargetAndTransition;
  readonly whileTap?: TargetAndTransition;
  readonly transition?: Transition;
}

/** Hover feedback for a picture. It is not a control, so there is no press state. */
export function lift(reduced: boolean): Feedback {
  if (reduced) return {};
  return { whileHover: { scale: 1.015 }, transition: { duration: DURATION.press, ease: EASE_OUT } };
}

/** Hover and press feedback for something you can actually activate. */
export function pressable(reduced: boolean): Feedback {
  if (reduced) return {};
  return {
    whileHover: { scale: 1.012 },
    whileTap: { scale: 0.985 },
    transition: { duration: DURATION.press, ease: EASE_OUT },
  };
}

export interface Disclosure {
  readonly initial: TargetAndTransition;
  readonly animate: TargetAndTransition;
  readonly exit: TargetAndTransition;
  readonly transition: Transition;
}

/**
 * Opening and closing a disclosure. Height is animated here, because the reveal is the point.
 * Asked for less motion, the content simply appears: nothing slides open, and nothing below it
 * is pushed down gradually.
 */
export function disclose(reduced: boolean): Disclosure {
  if (reduced) return { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: STILL };
  return {
    initial: { opacity: 0, height: 0 },
    animate: { opacity: 1, height: "auto" },
    exit: { opacity: 0, height: 0 },
    transition: { duration: DURATION.disclose, ease: EASE_OUT },
  };
}

export interface Arrival {
  readonly initial?: TargetAndTransition;
  readonly whileInView?: TargetAndTransition;
  readonly viewport?: { once: true; amount: number };
  readonly transition?: Transition;
}

/** A quarter of the thing has to be on screen, so the reader is looking at it when it arrives. */
const VIEWPORT = { once: true, amount: 0.25 } as const;

/**
 * A section arriving as it comes into view, once.
 *
 * Nothing here runs when the reader has asked for less motion, and nothing runs before the page
 * has mounted. Both return no animation at all rather than an instant one, because an animation
 * that waits to be scrolled to is also content that waits to be scrolled to, and a reader who
 * turned motion off should not have to scroll a section into view to find out what it says.
 *
 * `animated` is false until the page has mounted, and that is the point: Motion writes `initial`
 * into the server-rendered markup, so a page whose scripts never run would otherwise keep every
 * one of these sections at zero opacity for good. Before mount this animates nothing, which
 * leaves the content exactly as written.
 */
export function arrive(animated: boolean, reduced: boolean, delay = 0): Arrival {
  if (!animated || reduced) return {};
  return {
    initial: { opacity: 0, y: 8 },
    whileInView: { opacity: 1, y: 0 },
    viewport: VIEWPORT,
    transition: { duration: DURATION.enter, ease: EASE_OUT, delay },
  };
}

export interface InViewStagger {
  readonly initial?: "hidden";
  readonly whileInView?: "shown";
  readonly viewport?: { once: true; amount: number };
  readonly variants?: Variants;
}

/**
 * A list whose children arrive one just after another when the list is scrolled to, rather than
 * when the page loads. Pair with `item`. The keyword chips use it, so a category further down a
 * long report arrives as the reader reaches it instead of having happened above the fold.
 */
export function staggerInView(animated: boolean, reduced: boolean, step = 0.018): InViewStagger {
  if (!animated || reduced) return {};
  const transition: Transition = { duration: 0, staggerChildren: step };
  return {
    initial: "hidden",
    whileInView: "shown",
    viewport: VIEWPORT,
    variants: { hidden: {}, shown: { transition } },
  };
}

export interface Fan extends Arrival {
  readonly style?: { readonly rotate: number; readonly x: number };
}

/** Where each document in the stack ends up: a turn in degrees, and a step sideways in pixels. */
const FANNED = [
  { rotate: -8, x: -78 },
  { rotate: 0, x: 0 },
  { rotate: 8, x: 78 },
] as const;

/**
 * One document fanning out of the stack as the step arrives.
 *
 * Where the documents end up is the same however they got there, so a reader who asked for less
 * motion, or whose scripts never ran, sees three documents fanned rather than one on top of
 * another. Only the fanning out is animation.
 */
export function fan(animated: boolean, reduced: boolean, index: number): Fan {
  const settled = FANNED[index] ?? FANNED[1];
  if (!animated || reduced) return { style: settled };
  return {
    initial: { opacity: 0, rotate: 0, x: 0 },
    whileInView: { opacity: 1, ...settled },
    viewport: VIEWPORT,
    transition: { duration: DURATION.fan, ease: EASE_OUT, delay: index * 0.06 },
  };
}

/**
 * How far each plane of a branch picture travels, in pixels, across the band's whole pass up the
 * window, and how far it leans under the pointer.
 *
 * Small differences, not big ones: the eye reads the difference between the planes as distance,
 * and past about this much it starts reading as shapes sliding around instead. `sky` lags the
 * page, `fore` runs ahead of it, and the caption never moves at all.
 *
 * No plane travels further than the bleed the stylesheet gives it, which is how the resting
 * picture can move without ever exposing an edge. `motion.test.ts` holds that line.
 */
export const PARALLAX: Record<Plane, { readonly scroll: number; readonly pointer: number }> = {
  sky: { scroll: 14, pointer: 2 },
  mid: { scroll: 6, pointer: 4 },
  fore: { scroll: -8, pointer: 6 },
};

/** How far a plane hangs over each edge of its frame, in pixels. `--plane-bleed` in the CSS. */
export const PLANE_BLEED = 10;

/** The furthest any one plane moves from where it is drawn. */
export const travelOf = (plane: Plane) => Math.abs(PARALLAX[plane].scroll) / 2 + PARALLAX[plane].pointer;

/**
 * When one cell of the "read by block" grid lights, as a fraction of that step's pass up the
 * window. Every cell is lit well before the step leaves, so nobody scrolls past a half-read form.
 */
export function cellWindow(index: number, count: number): [number, number] {
  const start = 0.12 + (index / count) * 0.56;
  return [start, start + 0.12];
}

export interface Play {
  readonly initial: TargetAndTransition;
  readonly animate: TargetAndTransition;
  readonly transition: Transition;
}

/** 0 for a translation or a turn, 1 for a scale: where an actor is drawn. */
function restOf(key: string, ...values: (number | string | undefined)[]): number | string {
  if (values.some((value) => typeof value === "string")) return "0%";
  return key === "scale" ? 1 : 0;
}

/**
 * One actor's part in a vignette: in from `from`, settle where it is drawn, hold, out to `out`.
 *
 * Asked for less motion, the actor does not move at all. It fades up where it is drawn, holds,
 * and fades out, which is the same scene as a still photograph of the moment after. That is why
 * the art is drawn settled rather than at its entrance.
 */
export function vignette(reduced: boolean, beat: Beat): Play {
  const { delay, travel, hold } = beat;

  if (reduced) {
    const stay = travel + hold;
    const total = DURATION.crossFade * 2 + stay;
    return {
      initial: { opacity: 0 },
      animate: { opacity: [0, 1, 1, 0] },
      transition: {
        duration: total,
        times: [0, DURATION.crossFade / total, (DURATION.crossFade + stay) / total, 1],
        ease: "linear",
        delay,
      },
    };
  }

  const total = travel + hold + LEAVE;
  const animate: Record<string, unknown> = { opacity: [0, 1, 1, 0] };
  for (const key of new Set([...Object.keys(beat.from), ...Object.keys(beat.out)]) as Set<keyof Offset>) {
    const rest = restOf(key, beat.from[key], beat.out[key]);
    animate[key] = [beat.from[key] ?? rest, rest, rest, beat.out[key] ?? rest];
  }

  return {
    initial: { opacity: 0, ...beat.from },
    animate: animate as TargetAndTransition,
    transition: {
      duration: total,
      times: [0, travel / total, (travel + hold) / total, 1],
      ease: [EASE_OUT, "linear", EASE_OUT],
      delay,
    },
  };
}

export interface Sweep {
  readonly animate: TargetAndTransition;
  readonly transition: Transition;
}

/**
 * The indeterminate progress bar. `null` when motion is reduced: the caller then shows a filled
 * bar that does not move, so the wait is still visible without anything sliding.
 */
export function sweep(reduced: boolean): Sweep | null {
  if (reduced) return null;
  return {
    animate: { x: ["-100%", "320%"] },
    transition: { duration: DURATION.progressSweep, ease: "easeInOut", repeat: Infinity },
  };
}
