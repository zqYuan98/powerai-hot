import "server-only";

import { headers } from "next/headers";

/** 访客看到的站点地址（经 Caddy 时带 X-Forwarded-Proto），用于接入说明里可以直接复制的完整 URL。 */
export async function siteOrigin(): Promise<string> {
  const h = await headers();
  const first = (v: string | null) => v?.split(",")[0]?.trim() || null;
  const host = first(h.get("x-forwarded-host")) ?? first(h.get("host")) ?? "localhost:3000";
  const local = /^(localhost|127\.|\[::1\])/.test(host);
  const proto = first(h.get("x-forwarded-proto")) ?? (local ? "http" : "https");
  return `${proto}://${host}`;
}
