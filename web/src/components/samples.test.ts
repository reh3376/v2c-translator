import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { SAMPLES } from "./samples";

const read = (relative: string) => readFileSync(new URL(relative, import.meta.url));

describe("sample documents", () => {
  it.each(SAMPLES.map((s) => s.name))("serves %s byte for byte as tests/fixtures has it", (name) => {
    expect(read(`../../public/samples/${name}`).equals(read(`../../../tests/fixtures/${name}`))).toBe(true);
  });
});
