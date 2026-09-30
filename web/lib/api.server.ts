import "server-only";

import { cookies, headers } from "next/headers";
import { notFound, redirect } from "next/navigation";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

type Query = Record<string, string | number | boolean | string[] | undefined | null>;

export function qs(params: Query): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x));
    else sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/** 服务端取数：转发会话 cookie 与访客 IP（后端按 IP 限频）；401 跳登录。404 返回 null，由调用方决定如何处理。 */
export async function apiOptional<T>(path: string, params: Query = {}): Promise<T | null> {
  const session = (await cookies()).get("pa_session");
  const forwarded = (await headers()).get("x-forwarded-for");
  const res = await fetch(`${BACKEND}/api${path}${qs(params)}`, {
    cache: "no-store",
    headers: {
      ...(session ? { cookie: `pa_session=${session.value}` } : {}),
      ...(forwarded ? { "x-forwarded-for": forwarded } : {}),
    },
  });
  if (res.status === 401) redirect("/login");
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${path} 返回 ${res.status}`);
  return (await res.json()) as T;
}

export async function api<T>(path: string, params: Query = {}): Promise<T> {
  const data = await apiOptional<T>(path, params);
  if (data === null) notFound();
  return data;
}
