/**
 * What this server is allowed to write about a translation: a request id and the kind of
 * failure. Nothing else reaches a log line.
 *
 * This is the test that matters most in hosted mode. Container logs are kept, shipped and
 * read by people who are not the veteran who uploaded the document, and a DD-214 carries
 * a name, a pay grade, a separation reason and often a social security number. A file
 * called `john_smith_dd214_final.pdf` is already a disclosure before anything is parsed,
 * and the CLI prints exactly that file name at the front of every extraction error.
 *
 * So the test drives the real route against the real console, with a file name and a file
 * body that are both unmistakable, and fails if either turns up anywhere.
 */

import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseConfig, type ServerConfig } from "./config";
import { handleTranslate, makeThrottle } from "./translate";

const systemTmp = os.tmpdir();

/**
 * Strings that must never appear in a log line. The number is `000-00-0000`, which is
 * one of `scripts/pii_guard.py`'s synthetic placeholders: a test about not leaking a
 * service number is no place to commit one.
 */
const NAME = "Sgt-Jane-Q-Veteran-dd214.txt";
const BODY = "Notes for my counselor. Jane Q Veteran, 000-00-0000. Nothing here is a form.";

let scratch: string;
let config: ServerConfig;
let lines: string[];

beforeEach(async () => {
  scratch = await mkdtemp(path.join(systemTmp, "log-test-"));
  config = parseConfig({ ...process.env, V2C_MODE: "local", V2C_TMPDIR: scratch });
  lines = [];
  const capture = (...args: unknown[]) => void lines.push(args.map(String).join(" "));
  for (const level of ["log", "info", "warn", "error", "debug", "trace"] as const) {
    vi.spyOn(console, level).mockImplementation(capture);
  }
});

afterEach(async () => {
  vi.restoreAllMocks();
  await rm(scratch, { recursive: true, force: true });
});

const run = (request: Request) => handleTranslate(request, config, makeThrottle(config));

function upload(files: File[]): Request {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return new Request("http://localhost/api/translate", { method: "POST", body: form });
}

const logged = () => lines.join("\n");

function expectNothingSensitive(): void {
  const all = logged();
  expect(all).not.toContain(NAME);
  expect(all).not.toContain("Jane");
  expect(all).not.toContain("000-00-0000");
  expect(all).not.toContain(BODY);
  expect(all).not.toContain(scratch);
  // The CLI's own words, which arrive on stderr behind the file name.
  expect(all).not.toContain("Unrecognised document");
  expect(all).not.toMatch(/\.txt|\.pdf|\.json/);
}

describe("what a failed translation writes to the log", () => {
  it("says nothing about a document the CLI could not read", async () => {
    const response = await run(upload([new File([BODY], NAME, { type: "text/plain" })]));

    expect(response.status).toBe(422);
    // The visitor is told which of their files failed. The log is not.
    expect(await response.json()).toMatchObject({ file: NAME });
    expectNothingSensitive();
  });

  it("says nothing about the documents when the CLI cannot be run at all", async () => {
    const broken = { ...config, cli: { ...config.cli, uv: path.join(scratch, "no-such-uv") } };

    const response = await handleTranslate(
      upload([new File([BODY], NAME, { type: "text/plain" })]),
      broken,
      makeThrottle(broken),
    );

    expect(response.status).toBe(500);
    expectNothingSensitive();
    expect(logged()).toMatch(/translate failed id=[0-9a-f]{8} kind=cli-error/);
  });

  it("says nothing about the documents when the CLI exits non-zero for its own reasons", async () => {
    const bin = await mkdtemp(path.join(systemTmp, "angry-uv-"));
    const angry = path.join(bin, "uv");
    // Prints the kind of line the real CLI prints, so the test proves the route drops it
    // rather than proving the CLI never says anything.
    await writeFile(angry, `#!/bin/sh\necho "${NAME}: ${BODY}" >&2\nexit 7\n`, { mode: 0o755 });

    try {
      const loud = { ...config, cli: { ...config.cli, uv: angry } };
      const response = await handleTranslate(
        upload([new File([BODY], NAME, { type: "text/plain" })]),
        loud,
        makeThrottle(loud),
      );

      expect(response.status).toBe(500);
      expectNothingSensitive();
      expect(logged()).toMatch(/translate failed id=[0-9a-f]{8} kind=cli-exit exit=7/);
    } finally {
      await rm(bin, { recursive: true, force: true });
    }
  });

  it("says nothing about a translation that times out", async () => {
    const bin = await mkdtemp(path.join(systemTmp, "slow-uv-"));
    const slow = path.join(bin, "uv");
    await writeFile(slow, "#!/bin/sh\nexec sleep 10\n", { mode: 0o755 });

    try {
      const stuck = { ...config, cli: { ...config.cli, uv: slow, timeoutMs: 200 } };
      const response = await handleTranslate(
        upload([new File([BODY], NAME, { type: "text/plain" })]),
        stuck,
        makeThrottle(stuck),
      );

      expect(response.status).toBe(504);
      expectNothingSensitive();
      expect(logged()).toMatch(/kind=cli-timeout/);
    } finally {
      await rm(bin, { recursive: true, force: true });
    }
  });
});

describe("what a successful translation writes to the log", () => {
  it("writes nothing at all", async () => {
    const fixtures = path.join(config.cli.repoRoot, "tests", "fixtures");
    const body = await (await import("node:fs/promises")).readFile(path.join(fixtures, "army_2000.txt"), "utf8");

    const response = await run(upload([new File([body], NAME, { type: "text/plain" })]));

    expect(response.status).toBe(200);
    expect(lines).toEqual([]);
  });
});

describe("what a turned-away visitor writes to the log", () => {
  it("never writes the address the limit is keyed on", async () => {
    const limited = parseConfig({
      ...process.env,
      V2C_MODE: "hosted",
      TURNSTILE_SITE_KEY: "1x00000000000000000000AA",
      TURNSTILE_SECRET_KEY: "1x0000000000000000000000000000000AA",
      V2C_TMPDIR: scratch,
      V2C_RATE_LIMIT: "1",
    });
    const throttle = makeThrottle(limited);
    const ip = "198.51.100.23";
    const ask = () => {
      const form = new FormData();
      form.append("files", new File([BODY], NAME, { type: "text/plain" }));
      return handleTranslate(
        new Request("http://localhost/api/translate", { method: "POST", body: form, headers: { "x-real-ip": ip } }),
        limited,
        throttle,
      );
    };

    await ask();
    const refused = await ask();

    expect(refused.status).toBe(429);
    expect(logged()).not.toContain(ip);
    expectNothingSensitive();
  });
});
