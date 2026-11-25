import { chmod, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { POST } from "@/app/api/translate/route";
import { cliConfig, handleTranslate, LIMITS } from "./translate";

const systemTmp = os.tmpdir();
const fixtures = path.join(cliConfig().repoRoot, "tests", "fixtures");

// The route makes its temp directories in TMPDIR, pointed at `scratch` for each test.
let scratch: string;
const leftovers = async () => (await readdir(scratch)).filter((name) => name.startsWith("dd214kw-"));

beforeEach(async () => {
  scratch = await mkdtemp(path.join(systemTmp, "route-test-"));
  process.env.TMPDIR = scratch;
});

afterEach(async () => {
  process.env.TMPDIR = systemTmp;
  await rm(scratch, { recursive: true, force: true });
});

function upload(files: File[]): Request {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return new Request("http://localhost/api/translate", { method: "POST", body: form });
}

const textFile = (name: string, body = "hello") => new File([body], name, { type: "text/plain" });

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

describe("POST /api/translate, limits", () => {
  it("asks for at least one document", async () => {
    const response = await POST(upload([]));

    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ ok: false, message: "Add at least one document." });
  });

  it(`refuses more than ${LIMITS.maxFiles} files before writing any`, async () => {
    const files = Array.from({ length: LIMITS.maxFiles + 1 }, (_, i) => textFile(`page-${i}.txt`));

    const response = await POST(upload(files));

    expect(response.status).toBe(400);
    expect(await response.json()).toMatchObject({ ok: false, message: expect.stringContaining("up to 10 files") });
    expect(await leftovers()).toEqual([]);
  });

  it("refuses a file over 10 MB and names it", async () => {
    const big = new File([new Uint8Array(LIMITS.maxFileBytes + 1)], "scan.pdf", { type: "application/pdf" });

    const response = await POST(upload([textFile("army_2000.txt"), big]));

    expect(response.status).toBe(413);
    expect(await response.json()).toEqual({ ok: false, file: "scan.pdf", message: "This file is larger than 10 MB." });
  });

  it("stops a translation that runs past the timeout and deletes its files", async () => {
    const bin = await mkdtemp(path.join(systemTmp, "slow-uv-"));
    const slowUv = path.join(bin, "uv");
    await writeFile(slowUv, "#!/bin/sh\nexec sleep 10\n");
    await chmod(slowUv, 0o755);

    try {
      const config = { ...cliConfig(), uv: slowUv, timeoutMs: 300 };
      const response = await handleTranslate(upload([textFile("army_2000.txt")]), config);

      expect(response.status).toBe(504);
      expect(await response.json()).toMatchObject({ ok: false, message: expect.stringContaining("stopped after") });
      expect(await leftovers()).toEqual([]);
    } finally {
      await rm(bin, { recursive: true, force: true });
    }
  });
});
