import { asset } from "@/base-path";
import { TranslateResult, type Engine } from "./types";

const UNREACHABLE: TranslateResult = {
  ok: false,
  message: "This page couldn't reach the translator. Try again in a moment.",
};

const UNREADABLE: TranslateResult = {
  ok: false,
  message: "The translator sent back a report this page can't read.",
};

/**
 * Posts the files to the app's own `/api/translate`, which runs the `dd214kw` CLI.
 *
 * Named for where the CLI runs relative to the route, not for the deploy mode: the same
 * engine serves the local app and the hosted one, and the only difference it sees is
 * whether there is a Turnstile token to send.
 */
export const localEngine: Engine = {
  async translate(files, turnstileToken) {
    const body = new FormData();
    for (const file of files) body.append("files", file);
    if (turnstileToken) body.append("turnstileToken", turnstileToken);
    let response: Response;
    try {
      response = await fetch(asset("/api/translate"), { method: "POST", body });
    } catch {
      return UNREACHABLE;
    }
    const parsed = TranslateResult.safeParse(await response.json().catch(() => null));
    return parsed.success ? parsed.data : UNREADABLE;
  },
};
