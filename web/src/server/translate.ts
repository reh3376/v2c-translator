import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { COPY, HOSTED_ONLY } from "@/content/copy";
import type { TranslateFailure } from "@/engine";
import type { CliConfig, ServerConfig } from "./config";
import { gate, type Gate, type Lease } from "./gate";
import { rateLimiter, type RateLimiter } from "./rate-limit";
import { message as turnstileMessage, verify } from "./turnstile";

const MB = 1024 * 1024;

/**
 * How long to tell a turned-away visitor to wait.
 *
 * A translation of a scanned page takes about five seconds, two run at once, and the
 * queue holds eight, so a full queue drains in roughly four rounds. Thirty seconds is
 * that, rounded up, and it is a hint rather than a promise.
 */
const QUEUE_RETRY_SECONDS = 30;

export type { CliConfig } from "./config";

/** The counters this process shares across requests. One container, one set. */
export interface Throttle {
  readonly gate: Gate;
  /** Null in local mode. */
  readonly limiter: RateLimiter | null;
}

export function makeThrottle(config: ServerConfig): Throttle {
  return {
    gate: gate(config.maxConcurrent, config.queueMax),
    limiter: config.rateLimit ? rateLimiter(config.rateLimit) : null,
  };
}

let shared: Throttle | undefined;

/** The throttle for this process, made once on the first translation. */
export function sharedThrottle(config: ServerConfig): Throttle {
  shared ??= makeThrottle(config);
  return shared;
}

type Upload = { original: string; saved: string; file: File };

type CliRun =
  | { kind: "ok"; stdout: string }
  | { kind: "exit"; code: number; stderr: string }
  | { kind: "timeout" }
  | { kind: "error"; message: string };

function failure(status: number, body: TranslateFailure, headers?: HeadersInit): Response {
  return Response.json(body, { status, headers });
}

/**
 * What goes into the container's log for a failure: a request id and the kind of thing
 * that went wrong, and on a non-zero exit the exit code.
 *
 * Nothing else, ever. Not the file name, which a veteran may well have called
 * `john_smith_dd214.pdf`; not the CLI's stderr, which starts with that file name; not
 * the error's own message, which may quote a path under the temp directory; not the
 * visitor's address. `logging.test.ts` asserts all of that against the real console.
 */
function logFailure(id: string, kind: string, exit?: number): void {
  console.error(`translate failed id=${id} kind=${kind}${exit === undefined ? "" : ` exit=${exit}`}`);
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

/**
 * How to run the CLI.
 *
 * The container installs `dd214kw` into a virtualenv and sets `DD214KW_BIN`, which is
 * the whole of what it needs: no `uv`, no repository, no lockfile resolution per
 * request. A developer's machine has none of that, so it goes through
 * `uv run --project <repoRoot>` exactly as before.
 */
export function command(config: CliConfig, args: string[]): { file: string; argv: string[] } {
  if (config.bin) return { file: config.bin, argv: args };
  return { file: config.uv, argv: ["run", "--quiet", "--project", config.repoRoot, "dd214kw", ...args] };
}

function runCli(config: CliConfig, cwd: string, args: string[]): Promise<CliRun> {
  const { file, argv } = command(config, args);
  const env = { ...process.env, COLUMNS: "10000", NO_COLOR: "1" };
  return new Promise((resolve) => {
    execFile(
      file,
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

/** What `-f json+md` prints: one extraction, both formats. See `render.to_bundle`. */
interface Bundle {
  readonly report: unknown;
  readonly markdown: string;
}

function isBundle(value: unknown): value is Bundle {
  if (typeof value !== "object" || value === null) return false;
  return "report" in value && typeof (value as Bundle).markdown === "string";
}

/** `--max-pages` refused a document. The CLI counts the pages; the sentence is this file's. */
const TOO_MANY_PAGES = /^too many pages: (\d+) \(limit (\d+)\)$/;

/**
 * The CLI exits 2 on a file it can't read, or won't, and prints `<file>: <message>` on
 * stderr. Each one is about a single file, so the answer names it as the visitor spelled
 * it rather than as it was saved, and never carries the temp directory.
 */
function fileFailure(
  stderr: string,
  uploads: Upload[],
  dir: string,
): { status: number; body: TranslateFailure } | null {
  for (const line of stderr.split("\n")) {
    const upload = uploads.find((u) => line.startsWith(`${u.saved}: `));
    if (!upload) continue;
    const message = line.slice(upload.saved.length + 2).replaceAll(dir, "").trim();
    const refused = TOO_MANY_PAGES.exec(message);
    if (refused) {
      return {
        status: 413,
        body: {
          ok: false,
          file: upload.original,
          message:
            `This file has ${refused[1]} pages; the translator reads up to ${refused[2]} per document. ` +
            "A DD-214 is 1-2 pages; send just those pages.",
        },
      };
    }
    return { status: 422, body: { ok: false, file: upload.original, message } };
  }
  return null;
}

/**
 * One `dd214kw translate`, which prints the report as JSON and as Markdown from a single
 * reading of the documents. It used to be two runs in parallel, one per format, which
 * OCR'd every scanned page twice: see the Sizing table in docs/deploy.md for what that
 * cost. The Markdown is rendered from the same report in memory, so the two cannot
 * disagree either.
 */
async function translate(uploads: Upload[], config: ServerConfig, dir: string, id: string): Promise<Response> {
  const generic = COPY[config.mode].genericFailure;
  const { maxPages } = config.limits;
  const args = ["translate", ...uploads.map((u) => u.saved), "--ocr", "-f", "json+md"];
  if (maxPages !== null) args.push("--max-pages", String(maxPages));
  const run = await runCli(config.cli, dir, args);

  if (run.kind === "timeout") {
    const seconds = config.cli.timeoutMs / 1000;
    logFailure(id, "cli-timeout");
    return failure(504, {
      ok: false,
      message: `The translator stopped after ${seconds} seconds. Try fewer files at a time.`,
    });
  }
  if (run.kind === "exit" && run.code === 2) {
    const refused = fileFailure(run.stderr, uploads, dir);
    if (refused) return failure(refused.status, refused.body);
  }
  if (run.kind !== "ok") {
    logFailure(id, `cli-${run.kind}`, run.kind === "exit" ? run.code : undefined);
    return failure(500, { ok: false, message: generic });
  }

  let bundle: unknown;
  try {
    bundle = JSON.parse(run.stdout);
  } catch {
    bundle = null;
  }
  if (!isBundle(bundle)) {
    logFailure(id, "cli-bad-json");
    return failure(500, { ok: false, message: generic });
  }
  return Response.json({ ok: true, report: bundle.report, markdown: bundle.markdown });
}

/**
 * The address this proxy set, and only in hosted mode.
 *
 * A client can send its own `X-Real-IP`, so the header is worth something only behind a
 * proxy that overwrites it, which is what the career site's Caddy does. Local mode reads
 * no header and limits nobody. An address that is somehow absent shares one bucket,
 * which is the safe way round: it limits more, not less.
 */
function visitor(request: Request, config: ServerConfig): string | null {
  if (config.mode !== "hosted") return null;
  return request.headers.get("x-real-ip")?.trim() || "unproxied";
}

/** POST /api/translate: multipart `files` in, the dd214kw report out. Nothing is kept. */
export async function handleTranslate(
  request: Request,
  config: ServerConfig,
  throttle: Throttle = sharedThrottle(config),
): Promise<Response> {
  const id = randomUUID().slice(0, 8);
  const { limits } = config;
  const generic = COPY[config.mode].genericFailure;

  const declared = Number(request.headers.get("content-length") ?? 0);
  if (declared > limits.maxBodyBytes) {
    return failure(413, {
      ok: false,
      message:
        `Send at most ${limits.maxBodyBytes / MB} MB at a time, ` +
        `up to ${limits.maxFiles} files of ${limits.maxFileBytes / MB} MB each.`,
    });
  }

  // Before the body is read, so a flood costs this server a header parse.
  const key = visitor(request, config);
  if (key && throttle.limiter) {
    const decision = throttle.limiter.take(key);
    if (!decision.ok) {
      return failure(
        429,
        { ok: false, message: HOSTED_ONLY.tooMany },
        { "retry-after": String(decision.retryAfterSeconds) },
      );
    }
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return failure(400, { ok: false, message: 'Send the documents as multipart/form-data, one "files" field each.' });
  }

  // Before a single byte is written, and before the gate is taken.
  if (config.mode === "hosted") {
    const token = form.get("turnstileToken");
    const verdict = await verify(typeof token === "string" ? token : null, config.turnstile.secretKey, {
      remoteIp: key === "unproxied" ? null : key,
    });
    if (!verdict.ok) {
      if (verdict.reason === "unreachable") logFailure(id, "turnstile-unreachable");
      return failure(verdict.reason === "unreachable" ? 503 : 403, {
        ok: false,
        message: turnstileMessage(verdict),
      });
    }
  }

  const files = form.getAll("files").filter((value): value is File => typeof value !== "string");
  if (files.length === 0) return failure(400, { ok: false, message: "Add at least one document." });
  if (files.length > limits.maxFiles) {
    return failure(400, {
      ok: false,
      message: `Translate up to ${limits.maxFiles} files at a time. You added ${files.length}.`,
    });
  }
  const tooBig = files.find((file) => file.size > limits.maxFileBytes);
  if (tooBig) {
    const message = `This file is larger than ${limits.maxFileBytes / MB} MB.`;
    return failure(413, { ok: false, file: tooBig.name, message });
  }

  // Taken before anything is written, so a waiting translation holds no temp files.
  const lease: Lease | null = await throttle.gate.enter();
  if (!lease) {
    return failure(503, { ok: false, message: HOSTED_ONLY.busy }, { "retry-after": String(QUEUE_RETRY_SECONDS) });
  }

  const uploads = toUploads(files);
  let dir: string | undefined;
  try {
    dir = await mkdtemp(path.join(config.tmpDir, "dd214kw-"));
    for (const upload of uploads) {
      const bytes = new Uint8Array(await upload.file.arrayBuffer());
      await writeFile(path.join(dir, upload.saved), bytes, { mode: 0o600 });
    }
    return await translate(uploads, config, dir, id);
  } catch {
    logFailure(id, "unexpected");
    return failure(500, { ok: false, message: generic });
  } finally {
    if (dir) await rm(dir, { recursive: true, force: true });
    lease.release();
  }
}
