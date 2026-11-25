import { describe, expect, it } from "vitest";
import { downloadName } from "./format";

const day = new Date(2026, 10, 25, 12, 0);

describe("downloadName", () => {
  it("names the report for the first file and the day", () => {
    expect(downloadName("army_2000.txt", "md", day)).toBe("army_2000-civilian-keywords-2026-11-25.md");
    expect(downloadName("army_2000.txt", "json", day)).toBe("army_2000-civilian-keywords-2026-11-25.json");
  });

  it("keeps spaces and hyphens and turns parentheses into hyphens", () => {
    expect(downloadName("DD-214 redac.pdf", "md", day)).toBe("DD-214 redac-civilian-keywords-2026-11-25.md");
    expect(downloadName("DD-214 (1).pdf", "md", day)).toBe("DD-214 -1-civilian-keywords-2026-11-25.md");
  });

  it("keeps letters from any script and replaces other symbols", () => {
    expect(downloadName("Résumé José.pdf", "md", day)).toBe("Résumé José-civilian-keywords-2026-11-25.md");
    expect(downloadName("Re\u0301sume\u0301.pdf", "md", day)).toBe("Résumé-civilian-keywords-2026-11-25.md");
    expect(downloadName("服役记录.pdf", "md", day)).toBe("服役记录-civilian-keywords-2026-11-25.md");
    expect(downloadName("a/b:c*?d😀e.final.txt", "md", day)).toBe("a-b-c-d-e-final-civilian-keywords-2026-11-25.md");
  });

  it("trims hyphens and spaces from both ends", () => {
    expect(downloadName(" --[draft] dd214-- .pdf", "md", day)).toBe("draft- dd214-civilian-keywords-2026-11-25.md");
  });

  it.each(["", ".pdf", "***.txt", "(((", "😀.pdf"])("falls back to documents for %j", (name) => {
    expect(downloadName(name, "md", day)).toBe("documents-civilian-keywords-2026-11-25.md");
  });

  it("caps the name at 60 characters", () => {
    expect(downloadName(`${"a".repeat(80)}.pdf`, "md", day)).toBe(`${"a".repeat(60)}-civilian-keywords-2026-11-25.md`);
    expect(downloadName(`${"b".repeat(59)} tail.pdf`, "md", day)).toBe(`${"b".repeat(59)}-civilian-keywords-2026-11-25.md`);
  });

  it("uses the local date at both ends of the day", () => {
    expect(downloadName("x.pdf", "md", new Date(2026, 0, 5, 0, 1))).toBe("x-civilian-keywords-2026-01-05.md");
    expect(downloadName("x.pdf", "md", new Date(2026, 11, 31, 23, 59))).toBe("x-civilian-keywords-2026-12-31.md");
  });
});
