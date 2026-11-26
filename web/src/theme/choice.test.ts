import { describe, expect, it } from "vitest";
import {
  BOOT_SCRIPT,
  CHOICE_LABELS,
  DEFAULT_CHOICE,
  STORAGE_KEY,
  THEME_ATTRIBUTE,
  THEME_CHOICES,
  applyChoice,
  currentChoice,
  parseChoice,
  readChoice,
  writeChoice,
  type ChoiceStore,
  type ThemeChoice,
} from "./choice";

/** A store that remembers, like `localStorage` on a good day. */
function store(initial?: string): ChoiceStore & { value: string | undefined } {
  return {
    value: initial,
    getItem(key) {
      return key === STORAGE_KEY ? (this.value ?? null) : null;
    },
    setItem(key, value) {
      if (key === STORAGE_KEY) this.value = value;
    },
  };
}

/** A store that refuses, like `localStorage` behind a blocked-cookies setting. */
const refusing: ChoiceStore = {
  getItem() {
    throw new DOMException("denied");
  },
  setItem() {
    throw new DOMException("denied");
  },
};

describe("the appearance choice", () => {
  it("offers system, light and dark, and labels each", () => {
    expect(THEME_CHOICES).toEqual(["system", "light", "dark"]);
    for (const choice of THEME_CHOICES) expect(CHOICE_LABELS[choice]).not.toBe("");
  });

  it("follows the system until the reader says otherwise", () => {
    expect(DEFAULT_CHOICE).toBe("system");
    expect(readChoice(store())).toBe("system");
  });

  it("reads back each choice it stored", () => {
    for (const choice of THEME_CHOICES) {
      const kept = store();
      expect(writeChoice(kept, choice)).toBe(true);
      expect(readChoice(kept)).toBe(choice);
    }
  });

  it("falls back to the system when storage holds something else", () => {
    for (const junk of ["", "DARK", "midnight", "null", "{}"]) {
      expect(parseChoice(junk), junk).toBe("system");
      expect(readChoice(store(junk)), junk).toBe("system");
    }
  });

  it("still works when storage is unavailable, and says it did not remember", () => {
    expect(readChoice(refusing)).toBe("system");
    expect(writeChoice(refusing, "dark")).toBe(false);
    expect(readChoice(null)).toBe("system");
    expect(writeChoice(undefined, "dark")).toBe(false);
  });

  it("puts the choice on the root element, which is all the stylesheet needs", () => {
    const attributes = new Map<string, string>();
    const root = {
      setAttribute: (name: string, value: string) => void attributes.set(name, value),
      getAttribute: (name: string) => attributes.get(name) ?? null,
    };
    applyChoice(root, "dark");
    expect(attributes.get(THEME_ATTRIBUTE)).toBe("dark");
    expect(currentChoice(root)).toBe("dark");
    applyChoice(root, "system");
    expect(currentChoice(root)).toBe("system");
  });

  it("reads an unwritten or tampered root element as following the system", () => {
    expect(currentChoice({ getAttribute: () => null })).toBe("system");
    expect(currentChoice({ getAttribute: () => "sepia" })).toBe("system");
  });
});

describe("the boot script", () => {
  /** Runs the script the way the browser does, against a stand-in document. */
  function boot(stored: string | null | { throws: true }): string | undefined {
    const attributes = new Map<string, string>();
    const localStorage = {
      getItem() {
        if (stored !== null && typeof stored === "object") throw new DOMException("denied");
        return stored;
      },
    };
    const document = {
      documentElement: { setAttribute: (name: string, value: string) => void attributes.set(name, value) },
    };
    new Function("localStorage", "document", BOOT_SCRIPT)(localStorage, document);
    return attributes.get(THEME_ATTRIBUTE);
  }

  it.each(THEME_CHOICES)("applies the stored choice %s before anything is painted", (choice: ThemeChoice) => {
    expect(boot(choice)).toBe(choice);
  });

  it("applies the system default when nothing is stored, when storage refuses, and when the value is junk", () => {
    expect(boot(null)).toBe("system");
    expect(boot({ throws: true })).toBe("system");
    expect(boot("sepia")).toBe("system");
  });

  it("is one small statement, because it runs ahead of the first paint", () => {
    expect(BOOT_SCRIPT.length).toBeLessThan(300);
    expect(BOOT_SCRIPT).not.toContain("\n");
  });
});
