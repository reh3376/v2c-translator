/**
 * How many translations run at once, and how many may wait.
 *
 * One translation runs `dd214kw translate` once, and a scanned page means tesseract in
 * it. On the box this is deployed to, a few of those are the whole memory budget of the
 * service, so the number is small and the overflow is explicit: past the queue, a visitor
 * is told to come back rather than joining a line that will time out anyway.
 *
 * In memory, and that is correct rather than a shortcut: there is one container, and if
 * there were two the gate would have to move to something both could see. `docs/deploy.md`
 * says so beside the `V2C_MAX_CONCURRENT` row.
 */

export interface Lease {
  /** Give the slot back. Safe to call more than once; later calls do nothing. */
  release(): void;
}

export interface Gate {
  /** A lease when there is room now or in the queue, null when the queue is full. */
  enter(): Promise<Lease | null>;
  /** Translations holding a slot. */
  readonly running: number;
  /** Translations waiting for one. */
  readonly waiting: number;
}

export function gate(maxConcurrent: number, queueMax: number): Gate {
  let running = 0;
  const waiting: ((lease: Lease) => void)[] = [];

  function lease(): Lease {
    let spent = false;
    return {
      release() {
        if (spent) return;
        spent = true;
        const next = waiting.shift();
        // Hand the slot straight on rather than counting it down and up again, so a
        // release can never let a third translation in past a queue of two.
        if (next) next(lease());
        else running -= 1;
      },
    };
  }

  return {
    async enter() {
      if (running < maxConcurrent) {
        running += 1;
        return lease();
      }
      if (waiting.length >= queueMax) return null;
      return new Promise<Lease>((resolve) => waiting.push(resolve));
    },
    get running() {
      return running;
    },
    get waiting() {
      return waiting.length;
    },
  };
}
