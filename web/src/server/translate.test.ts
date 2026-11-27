import { execFile } from "node:child_process";
import { chmod, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/translate/route";
import { HOSTED_ONLY } from "@/content/copy";
import { parseConfig, type Env, type ServerConfig } from "./config";
import { command, handleTranslate, makeThrottle } from "./translate";

// The real `execFile`, counted. How many times the CLI is started per upload is the whole
// of the memory and time one translation costs, so it is worth a test rather than a note.
vi.mock("node:child_process", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:child_process")>();
  return { ...actual, execFile: vi.fn(actual.execFile) };
});

const systemTmp = os.tmpdir();
const fixtures = path.join(parseConfig({}).cli.repoRoot, "tests", "fixtures");

// The route makes its temp directories in V2C_TMPDIR, pointed at `scratch` for each test.
let scratch: string;
const leftovers = async () => (await readdir(scratch)).filter((name) => name.startsWith("dd214kw-"));

let local: ServerConfig;

beforeEach(async () => {
  scratch = await mkdtemp(path.join(systemTmp, "route-test-"));
  process.env.TMPDIR = scratch;
  process.env.V2C_TMPDIR = scratch;
  local = parseConfig({ ...process.env, V2C_MODE: "local" });
});

afterEach(async () => {
  process.env.TMPDIR = systemTmp;
  delete process.env.V2C_TMPDIR;
  await rm(scratch, { recursive: true, force: true });
  vi.restoreAllMocks();
});

const PASS = "1x0000000000000000000000000000000AA"; // Cloudflare's documented always-pass test secret

function hosted(over: Env = {}): ServerConfig {
  return parseConfig({
    ...process.env,
    V2C_MODE: "hosted",
    TURNSTILE_SITE_KEY: "1x00000000000000000000AA",
    TURNSTILE_SECRET_KEY: PASS,
    ...over,
  });
}

function upload(files: File[], extra: Record<string, string> = {}, headers: HeadersInit = {}): Request {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  for (const [name, value] of Object.entries(extra)) form.append(name, value);
  return new Request("http://localhost/api/translate", { method: "POST", body: form, headers });
}

const textFile = (name: string, body = "hello") => new File([body], name, { type: "text/plain" });

/**
 * A PDF of `n` empty pages, and nothing else. Built here because no PDF is committed to
 * this repository, and empty because the page limit is checked before any page is read.
 */
function pdfOfPages(n: number, name = "long-scan.pdf"): File {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    `<< /Type /Pages /Count ${n} /Kids [${Array.from({ length: n }, (_, i) => `${i + 3} 0 R`).join(" ")}] >>`,
    ...Array.from({ length: n }, () => "<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>"),
  ];
  const offsets: number[] = [];
  let pdf = "%PDF-1.4\n";
  objects.forEach((object, i) => {
    offsets.push(pdf.length); // every byte of this file is ASCII, so length is the offset
    pdf += `${i + 1} 0 obj\n${object}\nendobj\n`;
  });
  const startxref = pdf.length;
  const entries = offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${entries}`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${startxref}\n%%EOF\n`;
  return new File([pdf], name, { type: "application/pdf" });
}

/** Cloudflare, answering yes to everything, without leaving this process. */
function cloudflareSaysYes(): void {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => Response.json({ success: true }));
}

const run = (request: Request, config: ServerConfig) => handleTranslate(request, config, makeThrottle(config));

describe("POST /api/translate, a file the CLI can't read", () => {
  it("names the file as it was uploaded and keeps the temp path out of the message", async () => {
    const sample = textFile("army_2000.txt", await readFile(path.join(fixtures, "army_2000.txt"), "utf8"));
    const name = "../Notes for my counselor, week of the 14th (final draft, long enough to wrap).txt";

    const response = await POST(upload([sample, textFile(name)]));

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({
      ok: false,
      file: name,
      message: "Unrecognised document: no extractor knows this layout.",
    });
    expect(await leftovers()).toEqual([]);
  });
});

describe("POST /api/translate, one reading of the documents", () => {
  it("starts the CLI once and answers with both the report and the Markdown", async () => {
    const started = vi.mocked(execFile);
    started.mockClear();
    const sample = textFile("army_2000.txt", await readFile(path.join(fixtures, "army_2000.txt"), "utf8"));

    const response = await run(upload([sample]), local);

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.markdown).toContain("# Civilian Workforce Keywords");
    expect(body.report.profile).toBeDefined();
    expect(started).toHaveBeenCalledTimes(1);
  });
});

describe("POST /api/translate, the page limit", () => {
  it("refuses a document longer than the limit, names it, and says what the limit is", async () => {
    const config = { ...local, limits: { ...local.limits, maxPages: 8 } };

    const response = await run(upload([pdfOfPages(14)]), config);

    expect(response.status).toBe(413);
    expect(await response.json()).toEqual({
      ok: false,
      file: "long-scan.pdf",
      message:
        "This file has 14 pages; the translator reads up to 8 per document. " +
        "A DD-214 is 1-2 pages; send just those pages.",
    });
    expect(await leftovers()).toEqual([]);
  });

  it("hands a document at the limit to the CLI, so the limit is the cap and not one below it", async () => {
    const config = { ...local, limits: { ...local.limits, maxPages: 2 } };
    const started = vi.mocked(execFile);
    started.mockClear();

    const response = await run(upload([pdfOfPages(2)]), config);

    // What this is about is that two pages are not refused for being three. What the CLI
    // then makes of two empty pages depends on whether this machine has OCR installed,
    // so the status is only asserted not to be the page limit's.
    expect(started).toHaveBeenCalledTimes(1);
    expect(response.status).not.toBe(413);
  });
});

describe("POST /api/translate, limits", () => {
  it("asks for at least one document", async () => {
    const response = await POST(upload([]));

    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ ok: false, message: "Add at least one document." });
  });

  it("refuses more than 10 files before writing any", async () => {
    const files = Array.from({ length: 11 }, (_, i) => textFile(`page-${i}.txt`));

    const response = await POST(upload(files));

    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ ok: false, message: expect.stringContaining("up to 10 files") });
    expect(await leftovers()).toEqual([]);
  });

  it("refuses a file over 10 MB and names it", async () => {
    const big = new File([new Uint8Array(local.limits.maxFileBytes + 1)], "scan.pdf", { type: "application/pdf" });

    const response = await POST(upload([textFile("army_2000.txt"), big]));

    expect(response.status).toBe(413);
    expect(await response.json()).toEqual({ ok: false, file: "scan.pdf", message: "This file is larger than 10 MB." });
  });

  it("caps the whole request much lower in hosted mode, on the declared length alone", async () => {
    const config = hosted({ V2C_MAX_BODY_MB: "4" });
    const request = upload([textFile("army_2000.txt")], {}, { "content-length": String(5 * 1024 * 1024) });

    const response = await run(request, config);

    expect(response.status).toBe(413);
    expect(await response.json()).toMatchObject({ message: expect.stringContaining("4 MB") });
  });

  it("stops a translation that runs past the timeout and deletes its files", async () => {
    const bin = await mkdtemp(path.join(systemTmp, "slow-uv-"));
    const slowUv = path.join(bin, "uv");
    await writeFile(slowUv, "#!/bin/sh\nexec sleep 10\n");
    await chmod(slowUv, 0o755);

    try {
      const config = { ...local, cli: { ...local.cli, uv: slowUv, timeoutMs: 300 } };
      const response = await run(upload([textFile("army_2000.txt")]), config);

      expect(response.status).toBe(504);
      expect(await response.json()).toMatchObject({ ok: false, message: expect.stringContaining("stopped after") });
      expect(await leftovers()).toEqual([]);
    } finally {
      await rm(bin, { recursive: true, force: true });
    }
  });
});

describe("how the CLI is reached", () => {
  it("runs an installed executable directly when the container points at one", () => {
    expect(command({ ...local.cli, bin: "/opt/v2c/bin/dd214kw" }, ["translate", "a.txt"])).toEqual({
      file: "/opt/v2c/bin/dd214kw",
      argv: ["translate", "a.txt"],
    });
  });

  it("goes through uv and the repository when there is none", () => {
    expect(command({ ...local.cli, bin: null, uv: "uv", repoRoot: "/repo" }, ["--version"])).toEqual({
      file: "uv",
      argv: ["run", "--quiet", "--project", "/repo", "dd214kw", "--version"],
    });
  });
});

describe("the robot check, in hosted mode", () => {
  it("refuses a request with no token and writes nothing", async () => {
    const asked = vi.spyOn(globalThis, "fetch");

    const response = await run(upload([textFile("army_2000.txt")]), hosted());

    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ message: HOSTED_ONLY.turnstileMissing });
    expect(asked).not.toHaveBeenCalled();
    expect(await leftovers()).toEqual([]);
  });

  it("refuses a token Cloudflare rejects and writes nothing", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      Response.json({ success: false, "error-codes": ["invalid-input-response"] }),
    );

    const response = await run(upload([textFile("a.txt")], { turnstileToken: "no" }), hosted());

    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ message: HOSTED_ONLY.turnstileRejected });
    expect(await leftovers()).toEqual([]);
  });

  it("answers 503 rather than letting anything through when Cloudflare is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      throw new Error("ECONNREFUSED");
    });

    const response = await run(upload([textFile("a.txt")], { turnstileToken: "x" }), hosted());

    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ message: HOSTED_ONLY.turnstileUnreachable });
    expect(await leftovers()).toEqual([]);
  });

  it("checks the token before it looks at the files at all", async () => {
    const asked = vi.spyOn(globalThis, "fetch");
    const eleven = Array.from({ length: 11 }, (_, i) => textFile(`page-${i}.txt`));

    const response = await run(upload(eleven), hosted());

    // Eleven files is a 400 in local mode; here the missing token is answered first,
    // because that is the check that has to come before any work.
    expect(response.status).toBe(403);
    expect(asked).not.toHaveBeenCalled();
  });

  it("translates when the token passes", async () => {
    cloudflareSaysYes();
    const sample = textFile("army_2000.txt", await readFile(path.join(fixtures, "army_2000.txt"), "utf8"));

    const response = await run(upload([sample], { turnstileToken: "XXXX.DUMMY.TOKEN.XXXX" }), hosted());

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ ok: true });
    expect(await leftovers()).toEqual([]);
  });

  it("asks nothing of Cloudflare in local mode", async () => {
    const asked = vi.spyOn(globalThis, "fetch");
    const sample = textFile("army_2000.txt", await readFile(path.join(fixtures, "army_2000.txt"), "utf8"));

    const response = await run(upload([sample]), local);

    expect(response.status).toBe(200);
    expect(asked).not.toHaveBeenCalled();
  });
});

describe("the per-visitor limit", () => {
  it("refuses the request past the limit with a Retry-After", async () => {
    const config = hosted({ V2C_RATE_LIMIT: "1", V2C_RATE_WINDOW_MINUTES: "5" });
    const throttle = makeThrottle(config);
    const from = { "x-real-ip": "203.0.113.9" };
    cloudflareSaysYes();
    const sample = await readFile(path.join(fixtures, "army_2000.txt"), "utf8");
    const ask = () =>
      handleTranslate(upload([textFile("army_2000.txt", sample)], { turnstileToken: "t" }, from), config, throttle);

    expect((await ask()).status).toBe(200);
    const refused = await ask();

    expect(refused.status).toBe(429);
    expect(refused.headers.get("retry-after")).toBe("300");
    expect(await refused.json()).toMatchObject({ message: HOSTED_ONLY.tooMany });
  });

  it("counts each address on its own", async () => {
    const config = hosted({ V2C_RATE_LIMIT: "1" });
    const throttle = makeThrottle(config);
    const ask = (ip: string) =>
      handleTranslate(upload([textFile("a.txt")], {}, { "x-real-ip": ip }), config, throttle);

    // No token, so both get 403: the point is that neither gets a 429.
    expect((await ask("203.0.113.1")).status).toBe(403);
    expect((await ask("203.0.113.2")).status).toBe(403);
    expect((await ask("203.0.113.1")).status).toBe(429);
  });

  it("limits nobody in local mode, whatever header arrives", async () => {
    const throttle = makeThrottle(local);
    const ask = () => handleTranslate(upload([], {}, { "x-real-ip": "203.0.113.1" }), local, throttle);

    for (let i = 0; i < 5; i++) expect((await ask()).status).toBe(400);
  });
});

describe("the queue", () => {
  it("turns away the request past the queue with a Retry-After", async () => {
    const config = hosted({ V2C_MAX_CONCURRENT: "1", V2C_QUEUE_MAX: "1" });
    const throttle = makeThrottle(config);
    cloudflareSaysYes();
    const sample = await readFile(path.join(fixtures, "army_2000.txt"), "utf8");
    const ask = () =>
      handleTranslate(upload([textFile("army_2000.txt", sample)], { turnstileToken: "t" }), config, throttle);

    // Started one at a time, so which of them reaches the gate first is not a question
    // about microtask order.
    const tick = () => new Promise((resolve) => setImmediate(resolve));
    const running = ask();
    await tick();
    const queued = ask();
    await tick();
    const refused = await ask();

    expect(refused.status).toBe(503);
    expect(refused.headers.get("retry-after")).toBe("30");
    expect(await refused.json()).toMatchObject({ message: HOSTED_ONLY.busy });
    expect((await running).status).toBe(200);
    expect((await queued).status).toBe(200);
    expect(await leftovers()).toEqual([]);
  });

  it("gives the slot back even when the translation fails", async () => {
    const config = hosted({ V2C_MAX_CONCURRENT: "1", V2C_QUEUE_MAX: "0" });
    const throttle = makeThrottle(config);
    cloudflareSaysYes();

    const first = await handleTranslate(upload([textFile("hello.txt")], { turnstileToken: "t" }), config, throttle);
    expect(first.status).toBe(422);

    const second = await handleTranslate(upload([textFile("hello.txt")], { turnstileToken: "t" }), config, throttle);
    expect(second.status).toBe(422);
  });
});
