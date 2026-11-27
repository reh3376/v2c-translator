/**
 * How this server is deployed, read from the environment once at boot.
 *
 * Two modes, and `local` is the default, so nothing an existing user runs changes:
 *
 * - **local** is the app on your own computer. It listens on 127.0.0.1, asks no bot
 *   check, limits nobody, and the privacy copy says the documents never leave the
 *   machine, because they don't.
 * - **hosted** is the app behind someone else's web server, open to anyone. It listens
 *   on 0.0.0.0 inside its container, verifies a Cloudflare Turnstile token before it
 *   writes a single byte, holds concurrent translations to a small number, and limits
 *   each visitor.
 *
 * Everything here is read at request or boot time, not baked into the build, so one
 * image runs in either mode. The single exception is `V2C_BASE_PATH`: Next.js resolves
 * `basePath` while it builds the client manifests, so the path the app is served under
 * is a property of the build. See `web/src/base-path.ts`.
 *
 * Hosted mode refuses to boot without both halves of the Turnstile pair. A site whose
 * page says it is bot-checked and whose server does not check is worse than one that
 * fails to start, and the same reasoning is written down in career-site's
 * `config.requireTurnstileInProduction`.
 */

import { homedir, tmpdir } from "node:os";
import path from "node:path";

export type Mode = "local" | "hosted";

const MB = 1024 * 1024;

/** Thrown when the environment asks for something this server cannot honour. */
export class ConfigError extends Error {}

export interface Limits {
  /** How many files one translation may carry. */
  readonly maxFiles: number;
  /** How large any one of them may be. */
  readonly maxFileBytes: number;
  /** How large the whole request may be. Hosted mode is stricter; see `parseConfig`. */
  readonly maxBodyBytes: number;
  /**
   * How many pages one document may have, or null for no limit. Pages are what drive
   * the memory and the time an OCR translation takes, so this is the number that makes
   * the ceiling a limit rather than a timeout. See [Sizing](../../../docs/deploy.md).
   */
  readonly maxPages: number | null;
  /** How long one `dd214kw translate` may run. */
  readonly timeoutMs: number;
}

export interface RateLimit {
  /** Translations allowed per window. */
  readonly max: number;
  readonly windowMs: number;
}

export interface Turnstile {
  /** Public half, rendered into the page at request time. */
  readonly siteKey: string;
  /** Private half, used only to verify a token server-side. */
  readonly secretKey: string;
}

export interface CliConfig {
  /**
   * The `dd214kw` executable, when one is installed. The container puts it on this
   * path, which skips `uv` and the repository entirely. Null on a developer's machine,
   * where `uv run --project <repoRoot>` is how the CLI is reached.
   */
  readonly bin: string | null;
  readonly repoRoot: string;
  readonly uv: string;
  readonly timeoutMs: number;
  /** Where the O*NET index is, spelled exactly as `DEFAULT_INDEX` in `src/dd214kw/index.py`. */
  readonly indexPath: string;
}

interface Deploy {
  readonly limits: Limits;
  /** Where temp directories for uploads are made. The container mounts a tmpfs here. */
  readonly tmpDir: string;
  /** Translations running at once. Each one runs one CLI process; see docs/deploy.md. */
  readonly maxConcurrent: number;
  /** Translations allowed to wait. Past this, a request gets 503 and a Retry-After. */
  readonly queueMax: number;
  readonly cli: CliConfig;
}

/**
 * A union on `mode`, so the compiler knows that hosted mode has a Turnstile pair and a
 * rate limit and local mode has neither. The route never has to ask whether a key it
 * needs is there, and no branch can forget the check.
 */
export type ServerConfig = Deploy &
  (
    | { readonly mode: "local"; readonly turnstile: null; readonly rateLimit: null }
    | { readonly mode: "hosted"; readonly turnstile: Turnstile; readonly rateLimit: RateLimit }
  );

/**
 * Any string map, not `NodeJS.ProcessEnv`, which this project types as requiring
 * `NODE_ENV`. Parsing is the boundary; past it everything is a `ServerConfig`.
 */
export type Env = Readonly<Record<string, string | undefined>>;

function mode(env: Env): Mode {
  const value = env.V2C_MODE?.trim() || "local";
  if (value === "local" || value === "hosted") return value;
  throw new ConfigError(`V2C_MODE must be "local" or "hosted", not ${JSON.stringify(value)}.`);
}

function count(env: Env, name: string, fallback: number, least = 1): number {
  const raw = env[name]?.trim();
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < least) {
    throw new ConfigError(`${name} must be a whole number of at least ${least}, not ${JSON.stringify(raw)}.`);
  }
  return value;
}

function required(env: Env, name: string): string {
  const value = env[name]?.trim();
  if (!value) {
    throw new ConfigError(
      `V2C_MODE=hosted needs ${name}. Hosted mode is open to anyone, so it is bot-checked with ` +
        "Cloudflare Turnstile, and a server that cannot check refuses to start rather than " +
        "serve a page that claims it does.",
    );
  }
  return value;
}

/** Read one `ServerConfig` out of an environment. Pure, so the tests can hand it anything. */
export function parseConfig(env: Env = process.env): ServerConfig {
  const deployed = mode(env);
  const maxFiles = 10;
  const maxFileBytes = 10 * MB;
  const timeoutMs = 60_000;

  // Local mode keeps the cap it has always had: every file at its full size, plus a
  // megabyte for the multipart envelope. Hosted mode is much tighter, because the cap
  // decides how much memory a full queue can hold. 25 MB x (2 running + 8 waiting) is
  // 250 MB of request bodies, which fits the mem_limit in docs/deploy.md beside two
  // OCR translations. A 10 MB scan plus a text file still goes through.
  const maxBodyBytes =
    deployed === "hosted"
      ? count(env, "V2C_MAX_BODY_MB", 25) * MB
      : maxFiles * maxFileBytes + MB;

  // Hosted mode caps the pages in one document, because pages are what an OCR
  // translation costs and that cost is shared with everyone else using the server. Six
  // covers any single document a visitor should be sending (a DD-214 is 1-2 pages, a
  // VMET 2-4) and stays well inside the 60-second timeout: 27 seconds measured, against
  // a 60-second timeout, on a 2-core box. See Sizing in docs/deploy.md. Local mode has
  // one user, their own memory and no queue, so it caps nothing unless they ask for it.
  // Zero means no limit, in either mode.
  const pages = count(env, "V2C_MAX_PAGES", deployed === "hosted" ? 6 : 0, 0);

  const deploy: Deploy = {
    limits: { maxFiles, maxFileBytes, maxBodyBytes, maxPages: pages || null, timeoutMs },
    tmpDir: env.V2C_TMPDIR?.trim() || tmpdir(),
    maxConcurrent: count(env, "V2C_MAX_CONCURRENT", deployed === "hosted" ? 2 : 4),
    // Zero is a legitimate setting: no waiting at all, busy means busy.
    queueMax: count(env, "V2C_QUEUE_MAX", 8, 0),
    cli: {
      bin: env.DD214KW_BIN?.trim() || null,
      repoRoot: path.resolve(env.DD214KW_REPO_ROOT ?? path.join(process.cwd(), "..")),
      uv: env.DD214KW_UV ?? "uv",
      timeoutMs,
      indexPath:
        env.DD214KW_INDEX?.trim() || path.join(homedir(), ".local", "share", "dd214kw", "index.sqlite"),
    },
  };

  if (deployed === "local") return { ...deploy, mode: "local", turnstile: null, rateLimit: null };

  return {
    ...deploy,
    mode: "hosted",
    turnstile: {
      siteKey: required(env, "TURNSTILE_SITE_KEY"),
      secretKey: required(env, "TURNSTILE_SECRET_KEY"),
    },
    rateLimit: {
      max: count(env, "V2C_RATE_LIMIT", 10),
      windowMs: count(env, "V2C_RATE_WINDOW_MINUTES", 10) * 60_000,
    },
  };
}

let cached: ServerConfig | undefined;

/**
 * The config for this process, parsed once. `instrumentation.ts` calls this at boot, so
 * a misconfigured hosted deploy dies there rather than on a visitor's first upload.
 */
export function serverConfig(): ServerConfig {
  cached ??= parseConfig();
  return cached;
}

/** Only for tests: forget the parsed config so the next call reads the environment again. */
export function forgetConfig(): void {
  cached = undefined;
}
