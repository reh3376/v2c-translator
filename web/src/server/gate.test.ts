import { describe, expect, it } from "vitest";
import { gate } from "./gate";

/** Let every already-resolved promise run. */
const settle = () => new Promise((resolve) => setImmediate(resolve));

describe("the concurrency gate", () => {
  it("lets the first N through at once", async () => {
    const g = gate(2, 8);

    expect(await g.enter()).not.toBeNull();
    expect(await g.enter()).not.toBeNull();
    expect(g.running).toBe(2);
    expect(g.waiting).toBe(0);
  });

  it("makes the next one wait, and lets it in when a slot comes back", async () => {
    const g = gate(1, 8);
    const first = await g.enter();

    const second = g.enter();
    await settle();
    expect(g.waiting).toBe(1);

    first?.release();

    expect(await second).not.toBeNull();
    expect(g.running).toBe(1);
    expect(g.waiting).toBe(0);
  });

  it("turns away the request that would be one past the queue", async () => {
    const g = gate(1, 2);
    await g.enter();
    const queued = [g.enter(), g.enter()];
    await settle();

    expect(await g.enter()).toBeNull();
    expect(g.waiting).toBe(2);
    void queued;
  });

  it("never runs more than N even as a queue drains", async () => {
    const g = gate(2, 8);
    const held = [await g.enter(), await g.enter()];
    const queued = [g.enter(), g.enter(), g.enter()];
    await settle();

    const seen: number[] = [];
    held[0]?.release();
    held[1]?.release();
    await settle();
    seen.push(g.running);

    for (const waiting of queued) (await waiting)?.release();
    await settle();

    expect(seen).toEqual([2]);
    expect(g.running).toBe(0);
    expect(g.waiting).toBe(0);
  });

  it("ignores a lease released twice, so a double release frees no extra slot", async () => {
    const g = gate(1, 8);
    const lease = await g.enter();

    lease?.release();
    lease?.release();

    expect(g.running).toBe(0);
    expect(await g.enter()).not.toBeNull();
    expect(g.running).toBe(1);
  });

  it("hands a returned slot to the one that waited longest", async () => {
    const g = gate(1, 8);
    const first = await g.enter();
    const order: string[] = [];
    const a = g.enter().then(() => order.push("a"));
    const b = g.enter().then(() => order.push("b"));
    await settle();

    first?.release();
    await a;
    expect(order).toEqual(["a"]);
    void b;
  });
});
