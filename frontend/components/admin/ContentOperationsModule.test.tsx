import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ContentOperationsModule from "./ContentOperationsModule";
import { api } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: {
    digestNow: vi.fn(), weeklyNow: vi.fn(), createTopicReport: vi.fn(), retryReport: vi.fn(), retryCard: vi.fn(),
    listReports: vi.fn(), listCards: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("ContentOperationsModule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listReports.mockResolvedValue([
      { id: 41, type: "weekly", title: "失败周报", status: "失败" },
      { id: 42, type: "daily", title: "失败日报", status: "失败" },
    ]);
    mockedApi.listCards.mockResolvedValue([{
      id: 51, article_id: 7, category: "大模型", status: "失败", article: { title: "失败卡片", channel: "AI洞察", kind: "资讯" },
    }]);
    mockedApi.digestNow.mockResolvedValue({ id: 61, title: "新日报", total: 1 });
    mockedApi.weeklyNow.mockResolvedValue({ id: 62, title: "新周报", status: "生成中" });
    mockedApi.createTopicReport.mockResolvedValue({ id: 63, title: "主题研报", status: "生成中" });
    mockedApi.retryReport.mockResolvedValue({});
    mockedApi.retryCard.mockResolvedValue({});
  });

  it("renders all costly content operations and calls their API methods", async () => {
    render(<ContentOperationsModule />);

    await waitFor(() => expect(screen.getByText("失败周报")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "立即生成日报" }));
    fireEvent.click(screen.getByRole("button", { name: "生成本周周报" }));
    fireEvent.change(screen.getByPlaceholderText("输入主题"), { target: { value: "电网 AI" } });
    fireEvent.click(screen.getByRole("button", { name: "发起主题研报" }));
    fireEvent.click(screen.getByRole("button", { name: "重试报告：失败周报" }));
    fireEvent.click(screen.getByRole("button", { name: "重试卡片：失败卡片" }));

    await waitFor(() => {
      expect(mockedApi.digestNow).toHaveBeenCalledTimes(1);
      expect(mockedApi.weeklyNow).toHaveBeenCalledTimes(1);
      expect(mockedApi.createTopicReport).toHaveBeenCalledWith("电网 AI");
      expect(mockedApi.retryReport).toHaveBeenCalledWith(41);
      expect(mockedApi.retryCard).toHaveBeenCalledWith(51);
      expect(screen.getAllByText(/已提交/).length).toBeGreaterThan(0);
    });
  });

  it("prevents duplicate clicks and surfaces per-action failure", async () => {
    let resolveDigest!: (value: { id: number; title: string; total: number }) => void;
    mockedApi.digestNow.mockImplementation(() => new Promise((resolve) => { resolveDigest = resolve; }));
    render(<ContentOperationsModule />);

    const digestButton = await screen.findByRole("button", { name: "立即生成日报" });
    fireEvent.click(digestButton);
    fireEvent.click(digestButton);
    expect(mockedApi.digestNow).toHaveBeenCalledTimes(1);
    resolveDigest({ id: 70, title: "日报", total: 0 });
    await waitFor(() => expect(screen.getByText(/成功|已提交/)).toBeInTheDocument());

    mockedApi.weeklyNow.mockRejectedValueOnce(new Error("offline"));
    fireEvent.click(screen.getByRole("button", { name: "生成本周周报" }));
    await waitFor(() => expect(screen.getByText("操作失败，请检查后端连接或查看日志")).toBeInTheDocument());
  });

  it("preserves the topic input when topic creation fails", async () => {
    mockedApi.createTopicReport.mockRejectedValueOnce(new Error("offline"));
    render(<ContentOperationsModule />);

    const topicInput = await screen.findByPlaceholderText("输入主题");
    fireEvent.change(topicInput, { target: { value: "失败主题" } });
    fireEvent.click(screen.getByRole("button", { name: "发起主题研报" }));

    await waitFor(() => expect(screen.getByText("操作失败，请检查后端连接或查看日志")).toBeInTheDocument());
    expect(topicInput).toHaveValue("失败主题");
  });

  it("does not expose daily reports as retryable report tasks", async () => {
    render(<ContentOperationsModule />);

    await waitFor(() => expect(screen.getByText("失败周报")).toBeInTheDocument());
    expect(screen.queryByText("失败日报")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试报告：失败日报" })).not.toBeInTheDocument();
    expect(mockedApi.retryReport).not.toHaveBeenCalledWith(42);
  });
});
