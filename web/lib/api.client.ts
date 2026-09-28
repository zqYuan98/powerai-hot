/** 浏览器端调用（同源 /api，由 Caddy 或 Next 代理到后端）。 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function send<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: init.method ?? (init.body === undefined ? "GET" : "POST"),
    headers: init.body === undefined ? {} : { "Content-Type": "application/json" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    credentials: "same-origin",
  });
  if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
    // 会话过期：整页跳转以丢弃所有客户端状态（此模块不在组件内，无法使用 router）
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
  }
  if (!res.ok) {
    let detail = `请求失败（${res.status}）`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") detail = data.detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}
