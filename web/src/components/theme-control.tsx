"use client";

import { useRef, useSyncExternalStore } from "react";
import {
  CHOICE_LABELS,
  DEFAULT_CHOICE,
  THEME_ATTRIBUTE,
  THEME_CHOICES,
  applyChoice,
  currentChoice,
  writeChoice,
  type ThemeChoice,
} from "@/theme/choice";

/** How long the page cross-fades from one theme to the other. Skipped under reduced motion. */
const FADE_MS = 160;

/** `<html data-theme>` is the one place the current choice lives, so the control reads it back. */
const themeStore = {
  subscribe(onChange: () => void) {
    const watch = new MutationObserver(onChange);
    watch.observe(document.documentElement, { attributeFilter: [THEME_ATTRIBUTE] });
    return () => watch.disconnect();
  },
  snapshot: () => currentChoice(document.documentElement),
  serverSnapshot: () => DEFAULT_CHOICE,
};

/**
 * System, Light, Dark, as three native radios.
 *
 * Native radios rather than buttons: one Tab stop for the group, arrow keys that move and choose,
 * and a grouping label, all without a line of key handling. Choosing writes `data-theme` on
 * `<html>` and remembers it; the stylesheet does the rest, and so does the operating system while
 * the choice is System.
 *
 * The boot script in `layout.tsx` has already applied the stored choice by the time this renders,
 * so the page never flashes the wrong colours.
 */
export function ThemeControl() {
  const choice = useSyncExternalStore(themeStore.subscribe, themeStore.snapshot, themeStore.serverSnapshot);
  const fading = useRef<number>(undefined);

  function pick(next: ThemeChoice) {
    writeChoice(window.localStorage, next);
    const root = document.documentElement;
    root.setAttribute("data-theme-switching", "");
    applyChoice(root, next);
    window.clearTimeout(fading.current);
    fading.current = window.setTimeout(() => root.removeAttribute("data-theme-switching"), FADE_MS * 2);
  }

  return (
    <fieldset className="appearance">
      <legend className="visually-hidden">Appearance</legend>
      {THEME_CHOICES.map((option) => (
        <label key={option} className="appearance-option">
          <input
            type="radio"
            name="appearance"
            value={option}
            checked={choice === option}
            onChange={() => pick(option)}
          />
          <span>{CHOICE_LABELS[option]}</span>
        </label>
      ))}
    </fieldset>
  );
}
