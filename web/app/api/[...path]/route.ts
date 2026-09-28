import type { NextRequest } from "next/server";

/**
 * 同源 /api 代理（运行时读取 BACKEND_URL）。
 * 生产环境 Caddy 会把 /api 直接分流到后端，请求不会到这里；本地开发与未配反代时由它兜底。
 * 不用 next.config 的 rewrites：那里的目标地址在 build 时就被固化，运行时改环境变量无效。
 */
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const FORWARD_REQUEST = ["accept", "content-type", "cookie", "if-none-match"];
const DROP_RESPONSE = new Set(["connection", "content-encoding", "content-length", "transfer-encoding", "set-cookie"]);

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const target = `${BACKEND}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  let res: Response;
  try {
    res = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json({ detail: "后端服务不可用" }, { status: 502 });
  }
  const out = new Headers();
  res.headers.forEach((value, key) => {
    if (!DROP_RESPONSE.has(key)) out.set(key, value);
  });
  for (const cookie of res.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(res.status === 204 || res.status === 304 ? null : res.body, { status: res.status, headers: out });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST, proxy as PUT };
