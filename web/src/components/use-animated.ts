"use client";

import { useSyncExternalStore } from "react";

/** Nothing ever changes, so nothing ever needs telling about it. */
const subscribe = () => () => {};

/**
 * False on the server and through hydration, true afterwards.
 *
 * Motion writes an element's `initial` values into the markup it renders on the server, so a
 * section that fades in as it is scrolled to would stay invisible for good on a page whose
 * scripts never arrived. Gating every scroll-driven animation on this makes the page as written
 * the page without JavaScript: all of the text, none of the transforms.
 */
export function useAnimated(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
