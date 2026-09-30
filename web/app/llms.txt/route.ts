import type { NextRequest } from "next/server";

import { proxyTo } from "@/lib/proxy";

export const dynamic = "force-dynamic";

export function GET(req: NextRequest): Promise<Response> {
  return proxyTo(req, "/llms.txt");
}
