import { tmpdir } from "node:os";
import { describe, expect, it } from "vitest";
import { ConfigError, parseConfig, type Env } from "./config";

const HOSTED = {
  V2C_MODE: "hosted",
  TURNSTILE_SITE_KEY: "site",
  TURNSTILE_SECRET_KEY: "secret",
} satisfies Env;

describe("the deploy mode", () => {
  it("is local when nothing says otherwise", () => {
    const config = parseConfig({});

    expect(config.mode).toBe("local");
    expect(config.turnstile).toBeNull();
    expect(config.rateLimit).toBeNull();
  });

  it("refuses a mode it does not know, instead of guessing", () => {
    expect(() => parseConfig({ V2C_MODE: "staging" })).toThrow(ConfigError);
  });
});

describe("hosted mode and the Turnstile pair", () => {
  it("refuses to start without the secret half", () => {
    expect(() => parseConfig({ V2C_MODE: "hosted", TURNSTILE_SITE_KEY: "site" })).toThrow(
      /needs TURNSTILE_SECRET_KEY/,
    );
  });

  it("refuses to start without the public half, because the widget would never render", () => {
    expect(() => parseConfig({ V2C_MODE: "hosted", TURNSTILE_SECRET_KEY: "secret" })).toThrow(
      /needs TURNSTILE_SITE_KEY/,
    );
  });

  it("carries both halves when both are set", () => {
    expect(parseConfig(HOSTED).turnstile).toEqual({ siteKey: "site", secretKey: "secret" });
  });
});

describe("what hosted mode tightens", () => {
  it("limits each visitor, and local mode limits nobody", () => {
    expect(parseConfig(HOSTED).rateLimit).toEqual({ max: 10, windowMs: 600_000 });
    expect(parseConfig({}).rateLimit).toBeNull();
  });

  it("caps the whole request far below ten files at ten megabytes", () => {
    const hosted = parseConfig(HOSTED);
    const local = parseConfig({});

    expect(hosted.limits.maxBodyBytes).toBe(25 * 1024 * 1024);
    expect(local.limits.maxBodyBytes).toBe(101 * 1024 * 1024);
    expect(hosted.limits.maxFiles).toBe(local.limits.maxFiles);
    expect(hosted.limits.maxFileBytes).toBe(local.limits.maxFileBytes);
  });

  it("runs fewer translations at once", () => {
    expect(parseConfig(HOSTED).maxConcurrent).toBe(2);
    expect(parseConfig({}).maxConcurrent).toBe(4);
  });

  it("caps the pages in one document, where local mode caps none", () => {
    expect(parseConfig(HOSTED).limits.maxPages).toBe(6);
    expect(parseConfig({}).limits.maxPages).toBeNull();
  });

  it("takes the page limit from the environment, in either mode, and 0 means no limit", () => {
    expect(parseConfig({ ...HOSTED, V2C_MAX_PAGES: "4" }).limits.maxPages).toBe(4);
    expect(parseConfig({ V2C_MAX_PAGES: "4" }).limits.maxPages).toBe(4);
    expect(parseConfig({ ...HOSTED, V2C_MAX_PAGES: "0" }).limits.maxPages).toBeNull();
  });
});

describe("the knobs the deploy sets", () => {
  it("takes every limit from the environment", () => {
    const config = parseConfig({
      ...HOSTED,
      V2C_MAX_CONCURRENT: "3",
      V2C_QUEUE_MAX: "16",
      V2C_RATE_LIMIT: "4",
      V2C_RATE_WINDOW_MINUTES: "2",
      V2C_MAX_BODY_MB: "12",
      V2C_TMPDIR: "/tmp/v2c",
      DD214KW_BIN: "/opt/venv/bin/dd214kw",
    });

    expect(config.maxConcurrent).toBe(3);
    expect(config.queueMax).toBe(16);
    expect(config.rateLimit).toEqual({ max: 4, windowMs: 120_000 });
    expect(config.limits.maxBodyBytes).toBe(12 * 1024 * 1024);
    expect(config.tmpDir).toBe("/tmp/v2c");
    expect(config.cli.bin).toBe("/opt/venv/bin/dd214kw");
  });

  it("falls back to the system temp directory and to uv", () => {
    const config = parseConfig({});

    expect(config.tmpDir).toBe(tmpdir());
    expect(config.cli.bin).toBeNull();
    expect(config.cli.uv).toBe("uv");
  });

  it.each(["0", "-1", "2.5", "lots"])("refuses %s as a count rather than running with a surprise", (value) => {
    expect(() => parseConfig({ ...HOSTED, V2C_MAX_CONCURRENT: value })).toThrow(ConfigError);
  });
});
