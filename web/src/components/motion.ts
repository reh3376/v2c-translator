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

/** Seconds. */
export const DURATION = {
  enter: 0.24,
  disclose: 0.2,
  press: 0.12,
  /** One sweep of the indeterminate progress bar. Repeats, so it is paced, not quick. */
  progressSweep: 1.3,
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
