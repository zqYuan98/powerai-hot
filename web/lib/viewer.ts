import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

/** 当前请求是否为管理员（同一次渲染内只问一次后端）。访客看不到收藏、笔记、跟进与后台入口。 */
export const isAdmin = cache(async (): Promise<boolean> => {
  const session = (await cookies()).get("pa_session");
  try {
    const res = await fetch(`${BACKEND}/api/auth/me`, {
      cache: "no-store",
      headers: session ? { cookie: `pa_session=${session.value}` } : {},
    });
    return res.ok && ((await res.json()) as { admin?: boolean }).admin === true;
  } catch {
    return false;
  }
});
