import { describe, expect, it } from "vitest";
import { COPY, sentences, type Copy } from "./copy";

/**
 * The promise the page makes about a reader's documents has to match where they
 * actually go. These are the words that would be a lie in the other mode.
 */
const STAYS_PUT = [
  /on this computer/i,
  /never leaves?/i,
  /nothing is uploaded/i,
  /not uploaded/i,
  /offline/i,
];

const LEAVES = [/sent over HTTPS/i, /to this server/i, /upload a document/i, /on this server/i];

const found = (copy: Copy, patterns: RegExp[]) =>
  patterns.filter((pattern) => sentences(copy).some((sentence) => pattern.test(sentence)));

describe("the local copy", () => {
  const copy = COPY.local;

  it("says the documents stay on the computer, because they do", () => {
    expect(copy.privacy.heading).toBe("Stays on this computer");
    expect(found(copy, STAYS_PUT).length).toBeGreaterThan(0);
  });

  it("never tells a reader their documents are sent anywhere", () => {
    expect(found(copy, LEAVES)).toEqual([]);
  });
});

describe("the hosted copy", () => {
  const copy = COPY.hosted;

  it("says where the documents go, what is done with them, and when they are gone", () => {
    expect(copy.privacy.paragraphs[0]).toBe(
      "Your documents are sent over HTTPS to this server, read in memory, and deleted as soon as your report is ready. Nothing is stored, logged or shared.",
    );
  });

  it("tells a reader not to send what they would rather not send", () => {
    expect(copy.privacy.paragraphs).toContain("Don't upload a document you aren't comfortable sending.");
  });

  it("never claims the documents stay on the reader's computer", () => {
    expect(found(copy, STAYS_PUT)).toEqual([]);
  });

  it("drops the local app's advice to go and read a terminal", () => {
    expect(copy.genericFailure).not.toMatch(/terminal/i);
  });

  it("says scans are read with OCR, rather than asking the reader to install it", () => {
    expect(copy.dropzoneHint).toMatch(/Scans are read with OCR/);
    expect(copy.addDocumentsBody).not.toMatch(/when OCR is installed/);
  });
});

describe("both modes", () => {
  it.each(["local", "hosted"] as const)("%s says something for every sentence the page needs", (mode) => {
    for (const sentence of sentences(COPY[mode])) expect(sentence.trim().length).toBeGreaterThan(0);
  });

  it("word the two modes differently everywhere it matters", () => {
    const local = sentences(COPY.local);
    const hosted = sentences(COPY.hosted);

    expect(hosted).toHaveLength(local.length + 1); // hosted adds the "don't upload" line
    expect(hosted.filter((sentence) => local.includes(sentence))).toEqual([]);
  });
});
