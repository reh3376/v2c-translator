import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import type { TranslateFailure } from "@/engine";

const MB = 1024 * 1024;

export const LIMITS = { maxFiles: 10, maxFileBytes: 10 * MB, timeoutMs: 60_000 } as const;

export type CliConfig = { repoRoot: string; uv: string; timeoutMs: number };

export function cliConfig(env: NodeJS.ProcessEnv = process.env): CliConfig {
  return {
    repoRoot: path.resolve(env.DD214KW_REPO_ROOT ?? path.join(process.cwd(), "..")),
    uv: env.DD214KW_UV ?? "uv",
    timeoutMs: LIMITS.timeoutMs,
  };
}

type Upload = { original: string; saved: string; file: File };

type CliRun =
  | { kind: "ok"; stdout: string }
  | { kind: "exit"; code: number; stderr: string }
  | { kind: "timeout" }
  | { kind: "error"; message: string };

const GENERIC = "The translator stopped before it finished. The terminal running this app shows the details.";

function failure(status: number, body: TranslateFailure): Response {
  return Response.json(body, { status });
}

/** Each file with a name the CLI can be given safely: no directories, no leading dash or dot, unique. */
function toUploads(files: File[]): Upload[] {
  const taken = new Set<string>();
  return files.map((file) => {
    const base = file.name.split(/[\\/]/).pop() ?? "";
    const ext = path.extname(base).toLowerCase().replace(/[^.a-z0-9]/g, "");
    const stem =
      base
        .slice(0, base.length - path.extname(base).length)
        .replace(/[^\w .-]/g, "_")
        .replace(/^[\s.-]+/, "")
        .slice(0, 80) || "document";
    let saved = `${stem}${ext}`;
    for (let n = 2; taken.has(saved.toLowerCase()); n++) saved = `${stem}-${n}${ext}`;
    taken.add(saved.toLowerCase());
    return { original: file.name, saved, file };
  });
}

function runCli(config: CliConfig, cwd: string, args: string[]): Promise<CliRun> {
  const argv = ["run", "--quiet", "--project", config.repoRoot, "dd214kw", "translate", ...args];
  const env = { ...process.env, COLUMNS: "10000", NO_COLOR: "1" };
  return new Promise((resolve) => {
    execFile(
      config.uv,
      argv,
      { cwd, env, timeout: config.timeoutMs, maxBuffer: 32 * MB, encoding: "utf8" },
      (error, stdout, stderr) => {
        if (!error) resolve({ kind: "ok", stdout });
        else if (error.killed) resolve({ kind: "timeout" });
        else if (typeof error.code === "number") resolve({ kind: "exit", code: error.code, stderr });
        else resolve({ kind: "error", message: error.message });
      },
    );
  });
}

/** The CLI exits 2 on a file it can't read and prints `<file>: <message>` on stderr. */
function extractionError(stderr: string, uploads: Upload[], dir: string): TranslateFailure | null {
  for (const line of stderr.split("\n")) {
    const upload = uploads.find((u) => line.startsWith(`${u.saved}: `));
    if (upload) {
      const message = line.slice(upload.saved.length + 2).replaceAll(dir, "").trim();
      return { ok: false, file: upload.original, message };
    }
  }
  return null;
}

function logFailure(run: CliRun): void {
  const detail =
    run.kind === "exit" ? { code: run.code, stderr: run.stderr.trim().split("\n").at(-1) } : run;
  console.error("dd214kw translate failed", detail);
}

async function translate(uploads: Upload[], config: CliConfig, dir: string): Promise<Response> {
  const names = uploads.map((u) => u.saved);
  const [json, markdown] = await Promise.all([
    runCli(config, dir, [...names, "--ocr", "-f", "json"]),
    runCli(config, dir, [...names, "--ocr", "-f", "md"]),
  ]);
  if (json.kind === "timeout" || markdown.kind === "timeout") {
    const seconds = config.timeoutMs / 1000;
    return failure(504, { ok: false, message: `The translator stopped after ${seconds} seconds. Try fewer files at a time.` });
  }
  if (json.kind === "exit" && json.code === 2) {
    const error = extractionError(json.stderr, uploads, dir);
    if (error) return failure(422, error);
  }
  if (json.kind !== "ok") {
    logFailure(json);
    return failure(500, { ok: false, message: GENERIC });
  }
  if (markdown.kind !== "ok") {
    logFailure(markdown);
    return failure(500, { ok: false, message: GENERIC });
  }
  const report: unknown = JSON.parse(json.stdout);
  return Response.json({ ok: true, report, markdown: markdown.stdout });
}

/** POST /api/translate: multipart `files` in, the dd214kw report out. Nothing is kept. */
export async function handleTranslate(request: Request, config: CliConfig): Promise<Response> {
  const declared = Number(request.headers.get("content-length") ?? 0);
  if (declared > LIMITS.maxFiles * LIMITS.maxFileBytes + MB) {
    return failure(413, {
      ok: false,
      message: `Send at most ${LIMITS.maxFiles} files of up to ${LIMITS.maxFileBytes / MB} MB each.`,
    });
  }
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return failure(400, { ok: false, message: 'Send the documents as multipart/form-data, one "files" field each.' });
  }
  const files = form.getAll("files").filter((value): value is File => typeof value !== "string");
  if (files.length === 0) return failure(400, { ok: false, message: "Add at least one document." });
  if (files.length > LIMITS.maxFiles) {
    return failure(400, {
      ok: false,
      message: `Translate up to ${LIMITS.maxFiles} files at a time. You added ${files.length}.`,
    });
  }
  const tooBig = files.find((file) => file.size > LIMITS.maxFileBytes);
  if (tooBig) {
    const message = `This file is larger than ${LIMITS.maxFileBytes / MB} MB.`;
    return failure(413, { ok: false, file: tooBig.name, message });
  }

  const uploads = toUploads(files);
  let dir: string | undefined;
  try {
    dir = await mkdtemp(path.join(tmpdir(), "dd214kw-"));
    for (const upload of uploads) {
      const bytes = new Uint8Array(await upload.file.arrayBuffer());
      await writeFile(path.join(dir, upload.saved), bytes, { mode: 0o600 });
    }
    return await translate(uploads, config, dir);
  } catch (error) {
    console.error("dd214kw translate failed", error instanceof Error ? error.message : error);
    return failure(500, { ok: false, message: GENERIC });
  } finally {
    if (dir) await rm(dir, { recursive: true, force: true });
  }
}
