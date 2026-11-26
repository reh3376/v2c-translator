import { serverConfig } from "@/server/config";
import { handleTranslate } from "@/server/translate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function POST(request: Request): Promise<Response> {
  return handleTranslate(request, serverConfig());
}
