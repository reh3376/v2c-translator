/**
 * How many translations one visitor may ask for in a window.
 *
 * Keyed on the address Caddy puts in `X-Real-IP`, and only in hosted mode. The header is
 * trusted there and nowhere else: a client can send its own `X-Real-IP`, so the value is
 * worth something only when the proxy in front of this container overwrites it, which is
 * what career-site's Caddyfile already does for its own API with `header_up X-Real-IP
 * {remote_host}`. Local mode passes no key at all and nobody is limited.
 *
 * The address is used as a map key and is never written to a log, a report or an error.
 *
 * A fixed window, not a sliding one. It lets a visitor spend ten translations in the last
 * second of one window and ten in the first second of the next, which for this service is
 * twenty translations by someone who waited, not an attack. The simpler structure is worth
 * more here than the smoother edge.
 */

export interface Decision {
  readonly ok: boolean;
  /** Seconds until the window resets. Zero when the request is allowed. */
  readonly retryAfterSeconds: number;
}

export interface RateLimiter {
  /** Count one translation against `key`, and say whether it may proceed. */
  take(key: string): Decision;
  /** Visitors currently held in memory. */
  readonly size: number;
}

const ALLOWED: Decision = { ok: true, retryAfterSeconds: 0 };

/** Past this many visitors, expired windows are swept before the next one is added. */
const SWEEP_AT = 10_000;

export function rateLimiter(
  limits: { max: number; windowMs: number },
  clock: () => number = Date.now,
): RateLimiter {
  const windows = new Map<string, { count: number; resetAt: number }>();

  return {
    take(key) {
      const now = clock();
      const open = windows.get(key);
      if (!open || open.resetAt <= now) {
        if (windows.size >= SWEEP_AT) {
          for (const [held, window] of windows) if (window.resetAt <= now) windows.delete(held);
        }
        windows.set(key, { count: 1, resetAt: now + limits.windowMs });
        return ALLOWED;
      }
      if (open.count < limits.max) {
        open.count += 1;
        return ALLOWED;
      }
      return { ok: false, retryAfterSeconds: Math.max(1, Math.ceil((open.resetAt - now) / 1000)) };
    },
    get size() {
      return windows.size;
    },
  };
}
