import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FeedModule from "./FeedModule";
import { api } from "../../lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      listArticles: vi.fn(),
      articleChannels: vi.fn(),
      articleFreshness: vi.fn(),
      articleHotspots: vi.fn(),
      articleTimeline: vi.fn(),
      threadSummary: vi.fn(),
    },
  };
});

const mockedApi = vi.mocked(api);
const raw = (id: number, title = `情报 ${id}`) => ({
  id, title, summary: "摘要", tags: ["储能"], channel: "行业动态", org: "测试机构",
  hot: false, view_count: 0, relevance_score: 90, curated: true, kind: "资讯",
  tier: "T1", scored: true, is_cluster_main: true, related_count: 0,
  crawled_at: `2026-07-11T08:${String(id % 60).padStart(2, "0")}:00`,
});

const props = {
  pool: [], added: {}, onAdd: vi.fn(), onGoSub: vi.fn(), favIds: {},
  onToggleFav: vi.fn(), subKeywords: [],
};

describe("FeedModule bounded server feed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listArticles.mockResolvedValue({ items: [raw(1)], next_cursor: null, has_more: false, total: 1 });
    mockedApi.articleChannels.mockResolvedValue([
      { name: "行业动态", count: 1 }, { name: "国网规划", count: 0 },
      { name: "招标公告", count: 0 }, { name: "AI洞察", count: 0 },
      { name: "政策法规", count: 0 }, { name: "前沿论文", count: 0 },
      { name: "大模型动态", count: 0 }, { name: "落地案例", count: 0 },
    ]);
    mockedApi.articleFreshness.mockResolvedValue({ latest_crawled_at: "2026-07-11T08:00:00", added_24h: 1, curated_24h: 1 });
    mockedApi.articleHotspots.mockResolvedValue([]);
    mockedApi.articleTimeline.mockResolvedValue({
      latest_crawled_at: new Date().toISOString(),
      buckets: [
        { ts: new Date(Date.now() - 2 * 36e5).toISOString(), count: 3, curated: 1 },
        { ts: new Date(Date.now() - 36e5).toISOString(), count: 0, curated: 0 },
        { ts: new Date().toISOString(), count: 2, curated: 0 },
      ],
    });
    mockedApi.threadSummary.mockResolvedValue([]);
  });

  it("shows only curated articles by default", async () => {
    render(<FeedModule {...props} />);

    await waitFor(() => expect(mockedApi.listArticles).toHaveBeenCalledWith(
      expect.objectContaining({ view: "curated", window: "all" }),
    ));
  });

  it("does not expose low-score or noise views in the reader feed", async () => {
    render(<FeedModule {...props} />);

    await screen.findByText("情报 1");
    expect(screen.getAllByRole("button", { name: "全部" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "噪音" })).not.toBeInTheDocument();
  });

  it("never labels a non-curated analysis as a recommendation", async () => {
    mockedApi.listArticles.mockResolvedValue({
      items: [{ ...raw(2), curated: false, recommend_reason: "不建议关注" }],
      next_cursor: null,
      has_more: false,
      total: 1,
    });
    render(<FeedModule {...props} />);

    await screen.findByText("情报 2");
    expect(screen.queryByText("推荐理由")).not.toBeInTheDocument();
  });

  it("submits a real search and sends it to the server query", async () => {
    render(<FeedModule {...props} />);
    const search = await screen.findByRole("searchbox", { name: "搜索情报" });

    fireEvent.change(search, { target: { value: "储能 电网" } });
    fireEvent.keyDown(search, { key: "Enter", code: "Enter" });

    await waitFor(() => expect(mockedApi.listArticles).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "储能 电网", channel: "行业动态", limit: 30 }),
    ));
  });

  it("loads the next cursor page and appends unique articles", async () => {
    mockedApi.listArticles
      .mockResolvedValueOnce({ items: [raw(1)], next_cursor: "next-1", has_more: true, total: 2 })
      .mockResolvedValueOnce({ items: [raw(2)], next_cursor: null, has_more: false, total: 2 });
    render(<FeedModule {...props} />);

    await screen.findByText("情报 1");
    fireEvent.click(screen.getByRole("button", { name: /加载更多/ }));

    await screen.findByText("情报 2");
    expect(screen.getByText("情报 1")).toBeInTheDocument();
    expect(mockedApi.listArticles).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: "next-1" }));
    expect(screen.queryByRole("button", { name: /加载更多/ })).not.toBeInTheDocument();
  });

  it("keeps a successful list when auxiliary metadata fails", async () => {
    mockedApi.articleChannels.mockRejectedValueOnce(new Error("counts unavailable"));
    mockedApi.articleFreshness.mockRejectedValueOnce(new Error("freshness unavailable"));

    render(<FeedModule {...props} />);

    expect(await screen.findByText("情报 1")).toBeInTheDocument();
    expect(mockedApi.listArticles).toHaveBeenCalled();
  });

  it("keeps the existing list when refresh fails", async () => {
    mockedApi.listArticles
      .mockResolvedValueOnce({ items: [raw(1)], next_cursor: null, has_more: false, total: 1 })
      .mockRejectedValueOnce(new Error("refresh unavailable"));
    render(<FeedModule {...props} />);
    await screen.findByText("情报 1");

    fireEvent.click(await screen.findByRole("button", { name: /最新入库/ }));

    await waitFor(() => expect(mockedApi.listArticles).toHaveBeenCalledTimes(2));
    expect(screen.getByText("情报 1")).toBeInTheDocument();
  });

  it("grays cards already marked read in local storage", async () => {
    localStorage.setItem("pai:read:v1", JSON.stringify([1]));
    render(<FeedModule {...props} />);

    const title = await screen.findByText("情报 1");
    expect(title.closest("[data-read]")).not.toBeNull();
    localStorage.clear();
  });

  it("renders the ingest timeline with totals and no stale warning when fresh", async () => {
    render(<FeedModule {...props} />);

    await waitFor(() => expect(screen.getByText("入库时间线 · 近 48h")).toBeInTheDocument());
    expect(screen.getByText("共 5 条 · 精选 1")).toBeInTheDocument();
    expect(screen.queryByText(/无新入库/)).not.toBeInTheDocument();
  });

  it("warns when the latest ingest is older than two crawl cycles", async () => {
    const old = new Date(Date.now() - 5 * 36e5).toISOString();
    mockedApi.articleTimeline.mockResolvedValue({
      latest_crawled_at: old,
      buckets: [{ ts: old, count: 1, curated: 0 }],
    });
    render(<FeedModule {...props} />);

    await waitFor(() => expect(screen.getByText(/已 5 小时 无新入库/)).toBeInTheDocument());
  });

  it("offers to load new intel when the freshness heartbeat sees a newer ingest", async () => {
    vi.useFakeTimers();
    try {
      render(<FeedModule {...props} />);
      await vi.waitFor(() => expect(mockedApi.articleFreshness).toHaveBeenCalled());

      mockedApi.articleFreshness.mockResolvedValue({ latest_crawled_at: "2026-07-12T09:00:00", added_24h: 5, curated_24h: 2 });
      await vi.advanceTimersByTimeAsync(61_000);

      expect(screen.getByRole("button", { name: /有新情报入库/ })).toBeInTheDocument();
      const before = mockedApi.listArticles.mock.calls.length;
      fireEvent.click(screen.getByRole("button", { name: /有新情报入库/ }));
      await vi.waitFor(() => expect(mockedApi.listArticles.mock.calls.length).toBe(before + 1));
      expect(screen.queryByRole("button", { name: /有新情报入库/ })).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
