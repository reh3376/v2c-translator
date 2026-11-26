"use client";

import { useEffect, useRef, useState } from "react";
import { HOSTED_ONLY } from "@/content/copy";

/**
 * The Cloudflare Turnstile widget, shown only in hosted mode.
 *
 * It is the one thing on this page that comes from another host, which is why the
 * Content-Security-Policy names `challenges.cloudflare.com` only in hosted mode: a
 * reader running the app on their own computer loads nothing from anywhere.
 *
 * Rendered explicitly rather than by the `cf-turnstile` class, because the implicit mode
 * needs a global callback function in place before Cloudflare's script runs, and React
 * offers no honest way to promise that. Explicit rendering keeps the token inside this
 * component's state, where the form can read it.
 *
 * The token is single-use and expires. `expired-callback` and `error-callback` both drop
 * it, so a page left open overnight asks again rather than posting a token the server
 * will refuse.
 */

interface TurnstileApi {
  render(
    element: HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "error-callback": () => void;
      "expired-callback": () => void;
      theme: "auto";
    },
  ): string | undefined;
  remove(id: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

let loading: Promise<void> | undefined;

/** Fetch Cloudflare's script once per page, however many widgets ask for it. */
function loadApi(): Promise<void> {
  loading ??= new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("turnstile script failed")));
      return;
    }
    const script = document.createElement("script");
    script.src = SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("turnstile script failed")));
    document.head.append(script);
  });
  return loading;
}

export function TurnstileGate({
  siteKey,
  onToken,
  round,
}: {
  siteKey: string;
  /** The current token, or null when there isn't one. */
  onToken: (token: string | null) => void;
  /**
   * Bumped by the page after each translation. A token is good for one verification, so
   * the widget is torn down and drawn again to get the next one.
   */
  round: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let widget: string | undefined;
    let dropped = false;

    loadApi()
      .then(() => {
        if (dropped || !host.current || !window.turnstile) return;
        widget = window.turnstile.render(host.current, {
          sitekey: siteKey,
          callback: (token) => onToken(token),
          "error-callback": () => onToken(null),
          "expired-callback": () => onToken(null),
          theme: "auto",
        });
      })
      .catch(() => {
        if (!dropped) setFailed(true);
      });

    return () => {
      dropped = true;
      if (widget && window.turnstile) window.turnstile.remove(widget);
    };
  }, [siteKey, onToken, round]);

  return (
    <div className="robot-check">
      <p className="hint" id="robot-check-label">
        {failed ? HOSTED_ONLY.turnstileUnreachable : HOSTED_ONLY.turnstileLabel}
      </p>
      <div ref={host} aria-labelledby="robot-check-label" />
    </div>
  );
}
