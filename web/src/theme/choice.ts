/**
 * The appearance choice: what it can be, where it is kept, and how it reaches the page.
 *
 * Three states, not two. "System" is a real choice, not the absence of one: it means this page
 * follows the operating system, including when the reader changes that while the page is open.
 * `theme.css` turns the attribute this module writes into a `color-scheme`, which is what
 * `light-dark()` resolves against, so nothing here needs to know a single colour.
 *
 * The boot script below runs in `<head>`, before the first paint, so a reader who chose dark
 * never sees a white page flash. It is inline because a separate file would be a second request
 * ahead of the paint; the app's `script-src` already allows `'unsafe-inline'`, so the policy in
 * `next.config.ts` is unchanged.
 */

export const THEME_CHOICES = ["system", "light", "dark"] as const;

export type ThemeChoice = (typeof THEME_CHOICES)[number];

export const DEFAULT_CHOICE: ThemeChoice = "system";

/** Read and written by the boot script as well, so it is declared once here. */
export const STORAGE_KEY = "v2c-appearance";

/** The attribute `theme.css` keys off, on `<html>`. */
export const THEME_ATTRIBUTE = "data-theme";

export const CHOICE_LABELS: Record<ThemeChoice, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

/** What a stored string is worth. Anything else, including nothing, means follow the system. */
export function parseChoice(stored: string | null | undefined): ThemeChoice {
  return THEME_CHOICES.find((choice) => choice === stored) ?? DEFAULT_CHOICE;
}

/** The part of `Storage` this needs. Either method may throw, and in private windows they do. */
export interface ChoiceStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** The stored choice, or `system` when storage is unavailable or holds something unexpected. */
export function readChoice(store: ChoiceStore | null | undefined): ThemeChoice {
  try {
    return parseChoice(store?.getItem(STORAGE_KEY));
  } catch {
    return DEFAULT_CHOICE;
  }
}

/** Remembers the choice. Returns false when storage refused it, so this session still works. */
export function writeChoice(store: ChoiceStore | null | undefined, choice: ThemeChoice): boolean {
  try {
    store?.setItem(STORAGE_KEY, choice);
    return store !== null && store !== undefined;
  } catch {
    return false;
  }
}

/** The one thing that changes the page's colours. */
export function applyChoice(root: Pick<HTMLElement, "setAttribute">, choice: ThemeChoice): void {
  root.setAttribute(THEME_ATTRIBUTE, choice);
}

/** The choice in force, read back off the element the boot script wrote it to. */
export function currentChoice(root: Pick<HTMLElement, "getAttribute">): ThemeChoice {
  return parseChoice(root.getAttribute(THEME_ATTRIBUTE));
}

/**
 * The inline script for `<head>`. Built from the constants above, so the key and the attribute
 * cannot drift apart from the rest of this module.
 */
export const BOOT_SCRIPT =
  `(function(){var c;try{c=localStorage.getItem(${JSON.stringify(STORAGE_KEY)})}catch(e){}` +
  `document.documentElement.setAttribute(${JSON.stringify(THEME_ATTRIBUTE)},` +
  `${JSON.stringify(THEME_CHOICES)}.indexOf(c)<0?${JSON.stringify(DEFAULT_CHOICE)}:c)})()`;
