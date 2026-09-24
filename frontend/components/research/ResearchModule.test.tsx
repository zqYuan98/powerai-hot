import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ResearchModule from "./ResearchModule";
import { api } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: { listReports: vi.fn(), getReport: vi.fn(), createTopicReport: vi.fn(), weeklyNow: vi.fn(), retryReport: vi.fn() },
}));

const mockedApi = vi.mocked(api);

afterEach(() => { vi.useRealTimers(); });

describe("ResearchModule employee read state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listReports.mockResolvedValue([{ id: 11, type: "weekly", title: "本周周报", status: "完成", created_at: "2026-07-10T08:00:00" }]);
    mockedApi.getReport.mockResolvedValue({ id: 11, type: "weekly", title: "本周周报", status: "完成", created_at: "2026-07-10T08:00:00", content_md: "## 重点\n- 已完成读取", sections: [] });
  });

  it("renders report list and detail without employee generation or retry controls", async () => {
    render(<ResearchModule />);
    await waitFor(() => expect(mockedApi.getReport).toHaveBeenCalledWith(11));
    expect(screen.getAllByText("本周周报").length).toBeGreaterThan(0);
    expect(await screen.findByText("重点")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/输入研究主题/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "发起研究" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "生成本周周报" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
  });

  it("keeps the polling state visible for reports still being generated", async () => {
    mockedApi.getReport.mockResolvedValue({ id: 11, type: "weekly", title: "本周周报", status: "生成中", sections: [] });
    render(<ResearchModule />);
    await waitFor(() => expect(screen.getByText(/正在检索素材并撰写/)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
  });

  it("ignores a stale detail response after switching reports", async () => {
    let resolveFirst!: (detail: any) => void;
    let resolveSecond!: (detail: any) => void;
    mockedApi.listReports.mockResolvedValue([
      { id: 11, type: "weekly", title: "第一份报告", status: "完成" },
      { id: 12, type: "weekly", title: "第二份报告", status: "完成" },
    ]);
    mockedApi.getReport.mockImplementation((id: number) => new Promise((resolve) => {
      if (id === 11) resolveFirst = resolve;
      else resolveSecond = resolve;
    }));
    render(<ResearchModule />);

    await waitFor(() => expect(mockedApi.getReport).toHaveBeenCalledWith(11));
    fireEvent.click(screen.getByText("第二份报告"));
    await waitFor(() => expect(mockedApi.getReport).toHaveBeenCalledWith(12));

    resolveSecond({ id: 12, type: "weekly", title: "第二份报告", status: "完成", content_md: "## 新内容", sections: [] });
    expect(await screen.findByText("新内容")).toBeInTheDocument();
    resolveFirst({ id: 11, type: "weekly", title: "第一份报告", status: "完成", content_md: "## 旧内容", sections: [] });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText("旧内容")).not.toBeInTheDocument();
    expect(screen.getByText("新内容")).toBeInTheDocument();
  });

  it("clears the previous detail while a newly selected report loads", async () => {
    let resolveSecond!: (detail: any) => void;
    mockedApi.listReports.mockResolvedValue([
      { id: 11, type: "weekly", title: "第一份报告", status: "完成" },
      { id: 12, type: "weekly", title: "第二份报告", status: "完成" },
    ]);
    mockedApi.getReport.mockImplementation((id: number) => id === 11
      ? Promise.resolve({ id: 11, type: "weekly", title: "第一份报告", status: "完成", content_md: "## 旧内容", sections: [] })
      : new Promise((resolve) => { resolveSecond = resolve; }));
    render(<ResearchModule />);

    expect(await screen.findByText("旧内容")).toBeInTheDocument();
    fireEvent.click(screen.getByText("第二份报告"));
    expect(screen.queryByText("旧内容")).not.toBeInTheDocument();
    resolveSecond({ id: 12, type: "weekly", title: "第二份报告", status: "完成", content_md: "## 新内容", sections: [] });
    expect(await screen.findByText("新内容")).toBeInTheDocument();
  });

  it("does not start overlapping polling requests", async () => {
    vi.useFakeTimers();
    const pending: Array<(detail: any) => void> = [];
    mockedApi.listReports.mockResolvedValue([{ id: 11, type: "weekly", title: "生成中报告", status: "生成中" }]);
    mockedApi.getReport.mockImplementation(() => new Promise((resolve) => { pending.push(resolve); }));
    render(<ResearchModule />);

    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(mockedApi.getReport).toHaveBeenCalledTimes(1);
    pending[0]({ id: 11, type: "weekly", title: "生成中报告", status: "生成中", sections: [] });
    await act(async () => { await Promise.resolve(); });
    await act(async () => { vi.advanceTimersByTime(3000); await Promise.resolve(); });
    expect(mockedApi.getReport).toHaveBeenCalledTimes(2);
    await act(async () => { vi.advanceTimersByTime(3000); await Promise.resolve(); });
    expect(mockedApi.getReport).toHaveBeenCalledTimes(2);
  });

  it("does not show the empty selection fallback alongside a detail error", async () => {
    mockedApi.getReport.mockRejectedValueOnce(new Error("offline"));
    render(<ResearchModule />);

    await waitFor(() => expect(screen.getByText("报告详情加载失败，请稍后重试")).toBeInTheDocument());
    expect(screen.queryByText("选择左侧报告查看内容。")).not.toBeInTheDocument();
  });
});
