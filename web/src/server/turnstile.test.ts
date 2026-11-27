import { describe, expect, it, vi } from "vitest";
import { HOSTED_ONLY } from "@/content/copy";
import { message, verify } from "./turnstile";

const SECRET = "1x0000000000000000000000000000000AA"; // Cloudflare's documented always-pass test secret

const replies = (payload: unknown, init: ResponseInit = {}) =>
  vi.fn(async () => Response.json(payload, init)) as unknown as typeof globalThis.fetch;

describe("verifying a Turnstile token", () => {
  it("passes a token Cloudflare accepts", async () => {
    expect(await verify("a-token", SECRET, { fetch: replies({ success: true }) })).toEqual({ ok: true });
  });

  it("rejects a token Cloudflare refuses, and never repeats its error codes", async () => {
    const reply = replies({ success: false, "error-codes": ["invalid-input-response"] });

    const verdict = await verify("a-token", SECRET, { fetch: reply });

    expect(verdict).toEqual({ ok: false, reason: "rejected" });
    expect(message(verdict)).toBe(HOSTED_ONLY.turnstileRejected);
    expect(message(verdict)).not.toMatch(/invalid-input-response/);
  });

  it("rejects a missing token without asking Cloudflare anything", async () => {
    const reply = replies({ success: true });

    expect(await verify(null, SECRET, { fetch: reply })).toEqual({ ok: false, reason: "missing" });
    expect(await verify("", SECRET, { fetch: reply })).toEqual({ ok: false, reason: "missing" });
    expect(reply).not.toHaveBeenCalled();
  });

  it("fails closed when Cloudflare cannot be reached", async () => {
    const down = vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }) as unknown as typeof globalThis.fetch;

    expect(await verify("a-token", SECRET, { fetch: down })).toEqual({ ok: false, reason: "unreachable" });
  });

  it("fails closed on an HTTP error and on a body that is not JSON", async () => {
    const http500 = replies({}, { status: 500 });
    const nonsense = vi.fn(async () => new Response("<html>")) as unknown as typeof globalThis.fetch;

    expect(await verify("a-token", SECRET, { fetch: http500 })).toEqual({ ok: false, reason: "unreachable" });
    expect(await verify("a-token", SECRET, { fetch: nonsense })).toEqual({ ok: false, reason: "unreachable" });
  });

  it("fails closed when success is anything but the boolean true", async () => {
    for (const success of ["true", 1, null, undefined, {}]) {
      expect(await verify("a-token", SECRET, { fetch: replies({ success }) })).toEqual({
        ok: false,
        reason: "rejected",
      });
    }
  });
});

/** Records what `verify` posts, and answers yes. */
function recorder(): { sent: () => FormData; fetch: typeof globalThis.fetch } {
  let body: FormData | undefined;
  const fetch = vi.fn(async (_url: unknown, init: RequestInit | undefined) => {
    body = init?.body as FormData;
    return Response.json({ success: true });
  }) as unknown as typeof globalThis.fetch;
  return {
    sent() {
      if (!body) throw new Error("verify sent nothing");
      return body;
    },
    fetch,
  };
}

describe("what goes to Cloudflare", () => {
  it("sends the secret, the token and the visitor's address, and nothing else", async () => {
    const posted = recorder();

    await verify("a-token", SECRET, { remoteIp: "203.0.113.7", fetch: posted.fetch });

    expect([...posted.sent().keys()].sort()).toEqual(["remoteip", "response", "secret"]);
    expect(posted.sent().get("secret")).toBe(SECRET);
    expect(posted.sent().get("response")).toBe("a-token");
  });

  it("leaves the address out when the proxy gave none", async () => {
    const posted = recorder();

    await verify("a-token", SECRET, { fetch: posted.fetch });

    expect([...posted.sent().keys()].sort()).toEqual(["response", "secret"]);
  });
});
