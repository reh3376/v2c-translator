import { describe, expect, it } from "vitest";
import { contentSecurityPolicy, securityHeaders } from "./security-headers";

const TURNSTILE = "https://challenges.cloudflare.com";

const directive = (policy: string, name: string) =>
  policy
    .split("; ")
    .find((part) => part.startsWith(`${name} `) || part === name) ?? "";

describe("the local policy", () => {
  const policy = contentSecurityPolicy("local");

  it("lets the page load nothing from anywhere but this origin", () => {
    expect(policy).not.toContain("challenges.cloudflare.com");
    expect(directive(policy, "connect-src")).toBe("connect-src 'self'");
    expect(directive(policy, "script-src")).toBe("script-src 'self' 'unsafe-inline'");
    expect(directive(policy, "frame-src")).toBe("frame-src 'none'");
  });

  it("allows eval only while the dev server is running", () => {
    expect(contentSecurityPolicy("local")).not.toContain("'unsafe-eval'");
    expect(contentSecurityPolicy("local", { dev: true })).toContain("'unsafe-eval'");
  });
});

describe("the hosted policy", () => {
  const policy = contentSecurityPolicy("hosted");

  it("allows Turnstile on all three directives it needs, and no others", () => {
    expect(directive(policy, "script-src")).toContain(TURNSTILE);
    expect(directive(policy, "frame-src")).toBe(`frame-src ${TURNSTILE}`);
    expect(directive(policy, "connect-src")).toBe(`connect-src 'self' ${TURNSTILE}`);
    expect(directive(policy, "img-src")).not.toContain(TURNSTILE);
    expect(directive(policy, "style-src")).not.toContain(TURNSTILE);
    expect(directive(policy, "font-src")).not.toContain(TURNSTILE);
  });

  it("names no host but Cloudflare's challenge host", () => {
    const hosts = policy.match(/https?:\/\/[^\s;]+/g) ?? [];
    expect([...new Set(hosts)]).toEqual([TURNSTILE]);
  });

  /**
   * The career site's Caddy sends its own site-wide policy, and a browser given two of
   * these enforces both. So this one has to stand on its own: whichever of the two the
   * `/v2c*` handle ends up sending, the app still works. See docs/deploy.md.
   */
  it("stands on its own, needing nothing the site policy happens to allow", () => {
    for (const name of ["default-src", "script-src", "style-src", "img-src", "font-src", "connect-src", "frame-src"]) {
      expect(directive(policy, name)).not.toBe("");
    }
  });
});

describe("both policies", () => {
  it.each(["local", "hosted"] as const)("%s refuses to be framed and pins the rest", (mode) => {
    const policy = contentSecurityPolicy(mode);

    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("object-src 'none'");
    expect(policy).toContain("base-uri 'self'");
    expect(policy).toContain("form-action 'self'");
    expect(policy).toContain("default-src 'self'");
  });

  it.each(["local", "hosted"] as const)("%s sends the other two headers unchanged", (mode) => {
    expect(securityHeaders(mode)).toMatchObject({
      "referrer-policy": "no-referrer",
      "x-content-type-options": "nosniff",
    });
  });
});
