/**
 * Can this process actually translate anything?
 *
 * Health says the web server is up. Readiness says the three things behind it work: the
 * `dd214kw` executable, the O*NET index it looks every specialty up in, and the OCR tools
 * a scanned page is read with. An image built without the index would serve a perfectly
 * healthy page that failed on every upload, which is the failure this answers first.
 *
 * The OCR check is the same kind of failure one layer down. Both OCR tools write a
 * temporary file before they do any work, and this container's root filesystem is
 * read-only: if `TMPDIR` does not point at the tmpfs, a text PDF still translates and
 * every scan comes back with block 12 unread, which reads to a veteran as a fault in
 * their own document. So `dd214kw check-ocr` renders a blank page and reads it, in this
 * container's real temp directory, and a container that cannot do that is never ready.
 *
 * Cached, because the honest check spawns processes and a rollout script may poll this
 * every second. A pass is good for a minute; a fail is rechecked in five seconds, so a
 * container that comes good is not held down by its own cache.
 */

import { execFile } from "node:child_process";
import { stat } from "node:fs/promises";
import type { ServerConfig } from "./config";
import { command } from "./translate";

const PASS_MS = 60_000;
const FAIL_MS = 5_000;

export interface Readiness {
  readonly ready: boolean;
  /** `dd214kw --version` ran and exited 0. */
  readonly cli: boolean;
  /** The index file is there and not empty. */
  readonly index: boolean;
  /** The OCR tools rendered a blank test page and read it, in this process's temp dir. */
  readonly ocr: boolean;
}

/** The CLI answers `--version` without opening the index, so this proves only the install. */
export function cliResponds(config: ServerConfig): Promise<boolean> {
  const { file, argv } = command(config.cli, ["--version"]);
  return new Promise((resolve) => {
    execFile(file, argv, { timeout: 10_000 }, (error) => resolve(!error));
  });
}

/**
 * `dd214kw check-ocr`: it exits 0 when the tools ran, and when they are not installed at
 * all, which is an ordinary developer's machine and not a broken deploy. It exits 3 when
 * they are installed and could not run, which is the one this answers.
 *
 * Deliberately not run from the upload directory. A translation happens to run the CLI
 * with its working directory on the tmpfs, which is the last place Python looks for a
 * temp directory, so running this check from there would pass whatever `TMPDIR` said.
 */
export function ocrResponds(config: ServerConfig): Promise<boolean> {
  const { file, argv } = command(config.cli, ["check-ocr"]);
  return new Promise((resolve) => {
    execFile(file, argv, { timeout: 30_000 }, (error) => resolve(!error));
  });
}

async function indexPresent(config: ServerConfig): Promise<boolean> {
  try {
    return (await stat(config.cli.indexPath)).size > 0;
  } catch {
    return false;
  }
}

export async function probe(config: ServerConfig): Promise<Readiness> {
  const [cli, index, ocr] = await Promise.all([
    cliResponds(config),
    indexPresent(config),
    ocrResponds(config),
  ]);
  return { ready: cli && index && ocr, cli, index, ocr };
}

let held: { at: number; readiness: Readiness } | undefined;

export async function readiness(config: ServerConfig, now: number = Date.now()): Promise<Readiness> {
  const age = held ? now - held.at : Infinity;
  if (held && age < (held.readiness.ready ? PASS_MS : FAIL_MS)) return held.readiness;
  const readiness = await probe(config);
  held = { at: now, readiness };
  return readiness;
}

/** Only for tests: forget the cached answer. */
export function forgetReadiness(): void {
  held = undefined;
}
