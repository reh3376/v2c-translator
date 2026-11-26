/**
 * The Cloudflare Turnstile check that stands in front of a hosted translation.
 *
 * The hosted app is open to anyone, which means it is open to anything. One translation
 * is two OCR processes on a shared box, so an unguarded endpoint is a free CPU faucet.
 * A visitor's widget hands the page a token; this verifies that token with Cloudflare
 * before the route writes a single byte to disk.
 *
 * `verify` takes its `fetch` as an argument so the tests can drive every outcome
 * Cloudflare has: a pass, a fail with codes, a response that isn't JSON, and the network
 * being down. The last one matters most. A verifier that treats "Cloudflare is
 * unreachable" as a pass is not a verifier, so this fails closed.
 */

import { HOSTED_ONLY } from "@/content/copy";

const ENDPOINT = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

/** How long to wait on Cloudflare before giving up and failing the check. */
const TIMEOUT_MS = 10_000;

export type Verdict =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: "missing" | "rejected" | "unreachable" };

export const MISSING: Verdict = { ok: false, reason: "missing" };

/** What the page shows for each way the check can go wrong. Never Cloudflare's codes. */
const MESSAGES: Readonly<Record<Exclude<Verdict, { ok: true }>["reason"], string>> = {
  missing: HOSTED_ONLY.turnstileMissing,
  rejected: HOSTED_ONLY.turnstileRejected,
  unreachable: HOSTED_ONLY.turnstileUnreachable,
};

export function message(verdict: Verdict): string {
  return verdict.ok ? "" : MESSAGES[verdict.reason];
}

/**
 * Verify one token against one secret.
 *
 * `remoteIp` is passed through when the proxy gave us one, because Cloudflare uses it to
 * score the challenge. It is never logged and never stored.
 */
export async function verify(
  token: string | null,
  secretKey: string,
  options: { remoteIp?: string | null; fetch?: typeof globalThis.fetch } = {},
): Promise<Verdict> {
  if (!token) return MISSING;

  const body = new FormData();
  body.append("secret", secretKey);
  body.append("response", token);
  if (options.remoteIp) body.append("remoteip", options.remoteIp);

  const send = options.fetch ?? globalThis.fetch;
  let payload: unknown;
  try {
    const response = await send(ENDPOINT, {
      method: "POST",
      body,
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return { ok: false, reason: "unreachable" };
    payload = await response.json();
  } catch {
    return { ok: false, reason: "unreachable" };
  }

  const success = (payload as { success?: unknown } | null)?.success;
  return success === true ? { ok: true } : { ok: false, reason: "rejected" };
}
