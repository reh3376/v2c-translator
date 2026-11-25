import { TranslateResult, type Engine } from "./types";

const UNREACHABLE: TranslateResult = {
  ok: false,
  message: "This page couldn't reach the translator. Check that the app is still running, then try again.",
};

const UNREADABLE: TranslateResult = {
  ok: false,
  message: "The translator sent back a report this page can't read.",
};

/** Runs the dd214kw CLI on this computer through the app's own /api/translate route. */
export const localEngine: Engine = {
  async translate(files) {
    const body = new FormData();
    for (const file of files) body.append("files", file);
    let response: Response;
    try {
      response = await fetch("/api/translate", { method: "POST", body });
    } catch {
      return UNREACHABLE;
    }
    const parsed = TranslateResult.safeParse(await response.json().catch(() => null));
    return parsed.success ? parsed.data : UNREADABLE;
  },
};
