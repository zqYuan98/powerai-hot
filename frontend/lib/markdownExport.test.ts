import { describe, expect, it } from "vitest";
import { buildArticleMarkdown, markdownFilename } from "./markdownExport";

const base = {
  id: 7, title: "Test Title", summary: "摘要内容", channel: "AI洞察",
  relevanceScore: 88, url: "https://orig/a", sourceDomain: "orig",
  publishedLabel: "2026-07-12", recommendReason: "值得看",
  contentHtml: "<p>第一段</p><p>第二段 <strong>重点</strong></p>",
  meta: { titleZh: "测试标题" },
} as any;

describe("buildArticleMarkdown", () => {
  it("includes metadata, links and plain-text body", () => {
    const md = buildArticleMarkdown(base, "http://localhost:3000");
    expect(md).toContain("# 测试标题");
    expect(md).toContain("https://orig/a");
    expect(md).toContain("http://localhost:3000/items/7");
    expect(md).toContain("## AI 摘要");
    expect(md).toContain("第一段");
    expect(md).toContain("第二段 重点");
  });

  it("falls back when body missing", () => {
    const md = buildArticleMarkdown({ ...base, contentHtml: null }, "http://x");
    expect(md).toContain("（暂无正文，见原文链接）");
  });
});

describe("markdownFilename", () => {
  it("sanitizes and truncates", () => {
    expect(markdownFilename('a/b\\c:*?"<>|' + "长".repeat(80))).toMatch(/\.md$/);
    expect(markdownFilename("abc").length).toBeLessThanOrEqual(64);
  });
});
