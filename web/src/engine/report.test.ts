import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Report } from "./report";
import { TranslateResult } from "./types";

// `dd214kw translate tests/fixtures/army_2000.txt tests/fixtures/army_vmet.txt
//  tests/fixtures/army_2000_dd215.json -f json`, run from the repository root.
const cliJson: unknown = JSON.parse(
  readFileSync(new URL("./fixtures/army-report.json", import.meta.url), "utf8"),
);

describe("Report", () => {
  it("parses the CLI's JSON for the synthetic Army set without dropping a field", () => {
    const report = Report.parse(cliJson);

    expect(report).toEqual(cliJson);
    expect(report.matches.map((m) => m.code)).toEqual(["11B", "92Y"]);
    expect(report.keywords.experience.map((k) => k.term)).toContain("9+ Years Professional Experience");
  });

  it("rejects a report that is missing a keyword category", () => {
    const { keywords, ...rest } = Report.parse(cliJson);
    const { training, ...partial } = keywords;

    expect(training).not.toHaveLength(0);
    expect(Report.safeParse({ ...rest, keywords: partial }).success).toBe(false);
  });

  it("parses a route reply into a result with the report inside", () => {
    const reply = TranslateResult.parse({ ok: true, report: cliJson, markdown: "# Civilian Workforce Keywords" });

    expect(reply.ok && reply.report.profile.context?.branch).toBe("Army");
  });
});
