import { cliConfig, handleTranslate } from "@/server/translate";

export const runtime = "nodejs";

export function POST(request: Request): Promise<Response> {
  return handleTranslate(request, cliConfig());
}
