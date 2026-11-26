import { describe, expect, it } from "vitest";
import { ALL_LINKS, CRISIS_LINE, RESOURCE_GROUPS } from "./resources";

describe("the resource links", () => {
  it("are all https, so nothing is sent in the clear", () => {
    for (const href of ALL_LINKS) expect(new URL(href).protocol, href).toBe("https:");
  });

  it("carry no query string and no fragment, so they cannot track where the reader came from", () => {
    for (const href of ALL_LINKS) {
      const url = new URL(href);
      expect(url.search, href).toBe("");
      expect(url.hash, href).toBe("");
    }
  });

  it("appear once each", () => {
    expect(new Set(ALL_LINKS).size).toBe(ALL_LINKS.length);
  });

  it("point at a .gov or .mil site, or at one of four known exceptions", () => {
    // Three of these are federal programmes that have never been on a .gov name, and the fourth
    // is the charity the issue named. Adding a fifth should be a decision, so it fails here first.
    const allowed = new Set([
      "www.careeronestop.org", // the Department of Labor's own career site
      "www.mynextmove.org", // O*NET, sponsored by the Department of Labor
      "www.veteranscrisisline.net", // the VA's crisis line
      "www.hireheroesusa.org", // the charity the issue asked for by name
    ]);
    const other = ALL_LINKS.map((href) => new URL(href).hostname).filter(
      (host) => !/\.(gov|mil)$/.test(host) && !allowed.has(host),
    );
    expect(other).toEqual([]);
  });

  it("each have a title and a line saying what the reader gets", () => {
    for (const group of RESOURCE_GROUPS) {
      expect(group.links.length, group.heading).toBeGreaterThan(0);
      for (const link of group.links) {
        expect(link.title.trim(), link.href).not.toBe("");
        expect(link.blurb.trim(), link.href).not.toBe("");
      }
    }
  });

  it("are grouped under headings that differ", () => {
    const headings = RESOURCE_GROUPS.map((group) => group.heading);
    expect(new Set(headings).size).toBe(headings.length);
  });
});

describe("the crisis line", () => {
  it("says what veteranscrisisline.net says: dial 988, press 1, text 838255", () => {
    expect(CRISIS_LINE.dial).toBe("988");
    expect(CRISIS_LINE.press).toBe("1");
    expect(CRISIS_LINE.text).toBe("838255");
  });

  it("links to the official site", () => {
    expect(new URL(CRISIS_LINE.href).hostname).toBe("www.veteranscrisisline.net");
  });

  it("is one of the links the checker visits", () => {
    expect(ALL_LINKS).toContain(CRISIS_LINE.href);
  });
});
