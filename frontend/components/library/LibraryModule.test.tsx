import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LibraryModule from "./LibraryModule";
import { api } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: {
    listCards: vi.fn(),
    patchCard: vi.fn(),
    retryCard: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("LibraryModule employee collection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listCards.mockResolvedValue([{
      id: 31, article_id: 3, category: "大模型", status: "失败", note: null,
      problem: "问题", method: "方法", conclusion: "结论", power_relevance: "关联",
      article: { title: "原文标题", title_zh: "原文标题", url: "https://example.com/source", channel: "AI洞察", kind: "资讯" },
    }]);
    mockedApi.patchCard.mockResolvedValue({} as any);
  });

  it("shows failed cards as waiting for admin handling without a retry button", async () => {
    render(<LibraryModule />);

    await waitFor(() => expect(screen.getByText("原文标题")).toBeInTheDocument());
    expect(screen.getByText("等待管理员处理")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /重试生成/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /原文/ })).toHaveAttribute("href", "https://example.com/source");
  });

  it("keeps note editing and saving available", async () => {
    render(<LibraryModule />);
    await waitFor(() => expect(screen.getByText(/点击添加个人笔记/)).toBeInTheDocument());

    fireEvent.click(screen.getByText(/点击添加个人笔记/));
    const noteBox = screen.getAllByRole("textbox").find((element) => element.tagName === "TEXTAREA");
    expect(noteBox).toBeDefined();
    fireEvent.change(noteBox!, { target: { value: "我的备注" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(mockedApi.patchCard).toHaveBeenCalledWith(31, { note: "我的备注" }));
  });

  it("edits the card category through the badge select", async () => {
    render(<LibraryModule />);
    await waitFor(() => expect(screen.getByText("原文标题")).toBeInTheDocument());

    const select = screen.getByRole("combobox", { name: "卡片分类" });
    expect(select).toHaveValue("大模型");
    fireEvent.change(select, { target: { value: "视觉/OCR" } });

    await waitFor(() => expect(mockedApi.patchCard).toHaveBeenCalledWith(31, { category: "视觉/OCR" }));
    await waitFor(() => expect(mockedApi.listCards).toHaveBeenCalledTimes(2)); // 保存后刷新列表
  });

  it("shows an error when category change fails", async () => {
    mockedApi.patchCard.mockRejectedValueOnce(new Error("offline"));
    render(<LibraryModule />);
    await waitFor(() => expect(screen.getByText("原文标题")).toBeInTheDocument());

    fireEvent.change(screen.getByRole("combobox", { name: "卡片分类" }), { target: { value: "其他" } });
    await waitFor(() => expect(screen.getByText("分类修改失败，请稍后重试")).toBeInTheDocument());
  });

  it("shows a load error and allows retry instead of the normal empty state", async () => {
    mockedApi.listCards.mockRejectedValueOnce(new Error("offline"));
    render(<LibraryModule />);

    await waitFor(() => expect(screen.getByText("知识库加载失败，请稍后重试")).toBeInTheDocument());
    expect(screen.queryByText("知识库还是空的")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试加载" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试加载" }));
    await waitFor(() => expect(screen.getByText("原文标题")).toBeInTheDocument());
  });

  it("keeps the note draft in edit mode and shows an error when saving fails", async () => {
    mockedApi.patchCard.mockRejectedValueOnce(new Error("offline"));
    render(<LibraryModule />);
    await waitFor(() => expect(screen.getByText(/点击添加个人笔记/)).toBeInTheDocument());

    fireEvent.click(screen.getByText(/点击添加个人笔记/));
    const noteBox = screen.getAllByRole("textbox").find((element) => element.tagName === "TEXTAREA");
    fireEvent.change(noteBox!, { target: { value: "保留这份草稿" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(screen.getByText("笔记保存失败，请稍后重试")).toBeInTheDocument());
    const draftBox = screen.getAllByRole("textbox").find((element) => element.tagName === "TEXTAREA");
    expect(draftBox).toHaveValue("保留这份草稿");
    expect(screen.getByRole("button", { name: "保存" })).toBeInTheDocument();
  });

  it("keeps the newest query/category response when list requests resolve out of order", async () => {
    const pending: Array<{ category?: string; q?: string; resolve: (rows: any[]) => void }> = [];
    mockedApi.listCards.mockImplementation((category?: string, q?: string) => new Promise((resolve) => {
      pending.push({ category, q, resolve });
    }));
    render(<LibraryModule />);

    await waitFor(() => expect(pending).toHaveLength(1));
    const search = screen.getByPlaceholderText("搜索标题/问题/方法/结论/笔记，回车检索");
    fireEvent.change(search, { target: { value: "最新" } });
    fireEvent.keyDown(search, { key: "Enter", code: "Enter" });
    await waitFor(() => expect(pending).toHaveLength(2));
    fireEvent.click(screen.getByText("大模型"));
    await waitFor(() => expect(pending).toHaveLength(3));

    pending[2].resolve([{ id: 91, article_id: 9, category: "大模型", status: "完成", article: { title: "最新卡片", channel: "AI洞察", kind: "资讯" } }]);
    expect(await screen.findByText("最新卡片")).toBeInTheDocument();
    pending[1].resolve([{ id: 92, article_id: 9, category: "全部", status: "完成", article: { title: "旧卡片", channel: "AI洞察", kind: "资讯" } }]);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText("旧卡片")).not.toBeInTheDocument();
    expect(screen.getByText("最新卡片")).toBeInTheDocument();
  });

  it("does not reload the collection after a note save resolves post-unmount", async () => {
    let resolvePatch!: (card: any) => void;
    mockedApi.patchCard.mockImplementation(() => new Promise((resolve) => { resolvePatch = resolve; }));
    const view = render(<LibraryModule />);
    await waitFor(() => expect(screen.getByText(/点击添加个人笔记/)).toBeInTheDocument());

    fireEvent.click(screen.getByText(/点击添加个人笔记/));
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(mockedApi.patchCard).toHaveBeenCalledWith(31, { note: "" }));
    view.unmount();
    resolvePatch({});
    await act(async () => { await Promise.resolve(); });
    expect(mockedApi.listCards).toHaveBeenCalledTimes(1);
  });
});
