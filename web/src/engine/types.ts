import { z } from "zod";
import { Report } from "./report";

export const TranslateResult = z.discriminatedUnion("ok", [
  z.object({ ok: z.literal(true), report: Report, markdown: z.string() }),
  z.object({ ok: z.literal(false), file: z.string().optional(), message: z.string() }),
]);

export type TranslateResult = z.infer<typeof TranslateResult>;
export type TranslateFailure = Extract<TranslateResult, { ok: false }>;

export interface Engine {
  /**
   * `turnstileToken` is the proof-of-not-a-robot a hosted deploy asks for. Local mode
   * runs no check and passes null.
   */
  translate(files: File[], turnstileToken: string | null): Promise<TranslateResult>;
}
