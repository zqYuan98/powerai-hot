import type { NextRequest } from "next/server";

import { encodePath, proxyTo } from "@/lib/proxy";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxyTo(req, `/feed/${encodePath((await ctx.params).path)}`);
}
