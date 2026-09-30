import type { NextRequest } from "next/server";

import { encodePath, proxyTo } from "@/lib/proxy";

/** 同源 /api 代理，见 lib/proxy.ts。 */
export const dynamic = "force-dynamic";

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxyTo(req, `/api/${encodePath((await ctx.params).path)}`);
}

export { proxy as DELETE, proxy as GET, proxy as OPTIONS, proxy as PATCH, proxy as POST, proxy as PUT };
