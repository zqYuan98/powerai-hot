import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DigestModule from "./DigestModule";
import { api } from "../../lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../../lib/api", () => ({
  api: { listReports: vi.fn(), getReport: vi.fn(), digestNow: vi.fn(), getClusterArticles: vi.fn() },
  mapArticle: (raw: any) => ({ id: raw.id, title: raw.title, summary: raw.summary ?? "摘要", tags: [], channel: raw.channel ?? "AI洞察", org: raw.org ?? "国家电网", hot: false, kind: raw.kind ?? "资讯", accent: "blue" }),
}));

const mockedApi = vi.mocked(api);
const props = { added: {}, onAdd: vi.fn(), favIds: {}, onToggleFav: vi.fn() };

describe("DigestModule employee read state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listReports.mockResolvedValue([{ id: 21, type: "daily", title: "日报 · 2026-07-10", status: "完成" }]);
    mockedApi.getReport.mockResolvedValue({ id: 21, type: "daily", title: "日报 · 2026-07-10", status: "完成", created_at: "2026-07-10T07:00:00", sections: [{ name: "重点资讯", articles: [{ id: 3, title: "电网 AI 进展", summary: "摘要", channel: "AI洞察" }] }] });
  });

  it("renders daily report and article actions without an immediate generation control", async () => {
    render(<DigestModule {...props} />);
    await waitFor(() => expect(screen.getByText("电网 AI 进展")).toBeInTheDocument());
    expect(screen.getByTitle("收藏到我的知识库")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /立即生成/ })).not.toBeInTheDocument();
    expect(mockedApi.digestNow).not.toHaveBeenCalled();
  });

  it("directs employees to wait for the schedule or contact an administrator when empty", async () => {
    mockedApi.listReports.mockResolvedValue([]);
    render(<DigestModule {...props} />);
    await waitFor(() => expect(screen.getByText(/管理员|定时/)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /立即生成/ })).not.toBeInTheDocument();
  });

  it("shows only the load error when the report list request fails", async () => {
    mockedApi.listReports.mockRejectedValue(new Error("offline"));
    render(<DigestModule {...props} />);

    await waitFor(() => expect(screen.getByText("日报加载失败，请稍后重试")).toBeInTheDocument());
    expect(screen.queryByText("还没有日报")).not.toBeInTheDocument();
    expect(screen.queryByText(/如需提前生成/)).not.toBeInTheDocument();
  });

  it("ignores a stale detail response after switching daily reports", async () => {
    let resolveFirst!: (detail: any) => void;
    let resolveSecond!: (detail: any) => void;
    mockedApi.listReports.mockResolvedValue([
      { id: 21, type: "daily", title: "日报 · 2026-07-10", status: "完成" },
      { id: 22, type: "daily", title: "日报 · 2026-07-09", status: "完成" },
    ]);
    mockedApi.getReport.mockImplementation((id: number) => new Promise((resolve) => {
      if (id === 21) resolveFirst = resolve;
      else resolveSecond = resolve;
    }));
    render(<DigestModule {...props} />);

    await waitFor(() => expect(mockedApi.getReport).toHaveBeenCalledWith(21));
    fireEvent.click(screen.getByText("2026-07-09"));
    await waitFor(() => expect(mockedApi.getReport).toHaveBeenCalledWith(22));

    resolveSecond({ id: 22, type: "daily", title: "日报 · 2026-07-09", status: "完成", sections: [{ name: "新内容", articles: [] }] });
    expect(await screen.findByText("新内容")).toBeInTheDocument();
    resolveFirst({ id: 21, type: "daily", title: "日报 · 2026-07-10", status: "完成", sections: [{ name: "旧内容", articles: [] }] });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText("旧内容")).not.toBeInTheDocument();
    expect(screen.getByText("新内容")).toBeInTheDocument();
  });
});
