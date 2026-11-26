/**
 * Is this process serving? Nothing more.
 *
 * No CLI, no index, no file system: Docker's HEALTHCHECK and the compose healthcheck
 * call this every few seconds for the life of the container, so it has to cost nothing.
 * Whether the translator itself works is `/api/readyz`.
 */

import { serverConfig } from "@/server/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({ ok: true, mode: serverConfig().mode }, { headers: { "cache-control": "no-store" } });
}
