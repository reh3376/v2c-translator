import { z } from "zod";
import { Report } from "./report";

export const TranslateResult = z.discriminatedUnion("ok", [
  z.object({ ok: z.literal(true), report: Report, markdown: z.string() }),
  z.object({ ok: z.literal(false), file: z.string().optional(), message: z.string() }),
]);

export type TranslateResult = z.infer<typeof TranslateResult>;
export type TranslateFailure = Extract<TranslateResult, { ok: false }>;

export interface Engine {
  translate(files: File[]): Promise<TranslateResult>;
}
