import { describe, expect, it } from "vitest";
import { rateLimiter } from "./rate-limit";

const LIMITS = { max: 3, windowMs: 60_000 };

function stoppedClock(at = 1_000_000) {
  let now = at;
  return { now: () => now, advance: (ms: number) => (now += ms) };
}

describe("the per-visitor limit", () => {
  it("allows up to the limit and refuses the next one", () => {
    const clock = stoppedClock();
    const limiter = rateLimiter(LIMITS, clock.now);

    expect([1, 2, 3].map(() => limiter.take("a").ok)).toEqual([true, true, true]);
    expect(limiter.take("a").ok).toBe(false);
  });

  it("says how long to wait, rounded up and never zero", () => {
    const clock = stoppedClock();
    const limiter = rateLimiter(LIMITS, clock.now);
    for (let i = 0; i < 3; i++) limiter.take("a");

    expect(limiter.take("a").retryAfterSeconds).toBe(60);

    clock.advance(59_500);
    expect(limiter.take("a").retryAfterSeconds).toBe(1);
  });

  it("counts each visitor on their own", () => {
    const limiter = rateLimiter(LIMITS, stoppedClock().now);
    for (let i = 0; i < 3; i++) limiter.take("a");

    expect(limiter.take("a").ok).toBe(false);
    expect(limiter.take("b").ok).toBe(true);
  });

  it("opens a fresh window once the old one has passed", () => {
    const clock = stoppedClock();
    const limiter = rateLimiter(LIMITS, clock.now);
    for (let i = 0; i < 3; i++) limiter.take("a");
    expect(limiter.take("a").ok).toBe(false);

    clock.advance(60_000);

    expect(limiter.take("a")).toEqual({ ok: true, retryAfterSeconds: 0 });
  });

  it("does not grow without bound as visitors come and go", () => {
    const clock = stoppedClock();
    const limiter = rateLimiter(LIMITS, clock.now);
    for (let i = 0; i < 10_000; i++) limiter.take(`visitor-${i}`);
    expect(limiter.size).toBe(10_000);

    clock.advance(60_000);
    limiter.take("someone-new");

    expect(limiter.size).toBe(1);
  });
});
