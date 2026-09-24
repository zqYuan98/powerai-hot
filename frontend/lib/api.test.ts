import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, getAuthEpoch, subscribeUnauthorized } from "./api";

describe("same-origin api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }))));
  });

  it("uses the relative api base and same-origin credentials", async () => {
    await api.listArticles();
    expect(fetch).toHaveBeenCalledWith("/api/articles", expect.objectContaining({ credentials: "same-origin" }));
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init as RequestInit).headers).not.toHaveProperty("X-Admin-Token");
  });

  it("does not read public token or api base environment variables", async () => {
    vi.stubEnv("NEXT_PUBLIC_ADMIN_TOKEN", "secret");
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "https://external.invalid");
    await api.listArticles();
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/api/articles");
    expect((init as RequestInit).headers).not.toHaveProperty("X-Admin-Token");
  });

  it("encodes the complete bounded article query", async () => {
    await api.listArticles({
      channel: "AI洞察", q: "储能 & 电网", kind: "案例", minScore: 70,
      view: "curated", window: "24h", tag: "源/网", sort: "score",
      limit: 30, cursor: "abc-_", includeAll: true,
    });

    const url = new URL(String(vi.mocked(fetch).mock.calls[0][0]), "http://local");
    expect(url.pathname).toBe("/api/articles");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      channel: "AI洞察", q: "储能 & 电网", kind: "案例", min_score: "70",
      view: "curated", window: "24h", tag: "源/网", sort: "score",
      limit: "30", cursor: "abc-_", include_all: "true",
    });
  });

  it("uses the dedicated bounded subscription hits endpoint", async () => {
    await api.subscriptionHits(3);
    expect(fetch).toHaveBeenCalledWith(
      "/api/subscriptions/hits?limit=3",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("keeps page-only parameters out of channel counts", async () => {
    await api.articleChannels({ channel: "行业动态", cursor: "next", limit: 30, view: "curated" });
    const url = new URL(String(vi.mocked(fetch).mock.calls[0][0]), "http://local");
    expect(Object.fromEntries(url.searchParams)).toEqual({ view: "curated" });
  });

  it("maps session methods and only sends token in the POST body", async () => {
    await api.getSession();
    await api.createSession("admin", "top-secret");
    await api.deleteSession();
    const calls = vi.mocked(fetch).mock.calls;
    expect(calls[0][0]).toBe("/api/auth/session");
    expect(calls[1][0]).toBe("/api/auth/session");
    expect(calls[1][1]).toMatchObject({ method: "POST", credentials: "same-origin" });
    expect(JSON.parse(String((calls[1][1] as RequestInit).body))).toEqual({ scope: "admin", token: "top-secret" });
    expect(String(calls[1][0])).not.toContain("top-secret");
    expect(calls[2][0]).toBe("/api/auth/session");
    expect(calls[2][1]).toMatchObject({ method: "DELETE", credentials: "same-origin" });
  });

  it("retains structured HTTP status errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("busy", { status: 429 })));
    await expect(api.getSession()).rejects.toMatchObject({ status: 429 });
  });

  it("notifies non-auth 401 listeners and supports unsubscribe", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(new Response("expired", { status: 401 }))));
    const listener = vi.fn();
    const unsubscribe = subscribeUnauthorized(listener);
    await expect(api.listArticles()).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(getAuthEpoch());
    unsubscribe();
    await expect(api.listArticles()).rejects.toMatchObject({ status: 401 });
    await expect(api.getSession()).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
