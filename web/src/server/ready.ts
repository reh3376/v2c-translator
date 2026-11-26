/**
 * Can this process actually translate anything?
 *
 * Health says the web server is up. Readiness says the two things behind it are there:
 * the `dd214kw` executable, and the O*NET index it looks every specialty up in. An image
 * built without the index would serve a perfectly healthy page that failed on every
 * upload, which is the failure this answers.
 *
 * Cached, because the honest check spawns a process and a rollout script may poll this
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
}

/** The CLI answers `--version` without opening the index, so this proves only the install. */
export function cliResponds(config: ServerConfig): Promise<boolean> {
  const { file, argv } = command(config.cli, ["--version"]);
  return new Promise((resolve) => {
    execFile(file, argv, { timeout: 10_000 }, (error) => resolve(!error));
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
  const [cli, index] = await Promise.all([cliResponds(config), indexPresent(config)]);
  return { ready: cli && index, cli, index };
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
