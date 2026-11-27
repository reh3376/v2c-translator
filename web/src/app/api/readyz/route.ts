/**
 * Is the translator behind this page usable? 200 when the CLI and the index are both
 * there, 503 when either is missing, with which one it was.
 *
 * This is the check a rollout waits on. `/api/healthz` is the one the container runs
 * every few seconds.
 */

import { serverConfig } from "@/server/config";
import { readiness } from "@/server/ready";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const checks = await readiness(serverConfig());
  return Response.json(
    { ok: checks.ready, checks: { cli: checks.cli, index: checks.index } },
    { status: checks.ready ? 200 : 503, headers: { "cache-control": "no-store" } },
  );
}
