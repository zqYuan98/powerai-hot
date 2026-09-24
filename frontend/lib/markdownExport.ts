import type { Article } from "./types";

function htmlToText(html: string): string {
  if (typeof DOMParser === "undefined") {
    return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  }
  const doc = new DOMParser().parseFromString(html, "text/html");
  return (doc.body.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
}

export function buildArticleMarkdown(a: Article, origin: string): string {
  const title = a.meta?.titleZh || a.title;
  const body = a.contentHtml ? htmlToText(a.contentHtml) : "（暂无正文，见原文链接）";
  const lines: string[] = [
    `# ${title}`,
    "",
    `- 来源：${a.sourceDomain ?? "未知"}${a.publishedLabel ? ` · ${a.publishedLabel}` : ""}`,
    `- 频道：${a.channel}${typeof a.relevanceScore === "number" ? ` · 相关度 ${a.relevanceScore}` : ""}`,
    ...(a.url ? [`- 原文：${a.url}`] : []),
    `- 站内：${origin}/items/${a.id}`,
    "",
  ];
  if (a.summary) lines.push("## AI 摘要", "", a.summary, "");
  if (a.recommendReason) lines.push("## 推荐理由", "", a.recommendReason, "");
  lines.push("## 正文", "", body, "");
  return lines.join("\n");
}

export function markdownFilename(title: string): string {
  const safe = title.replace(/[/\\:*?"<>|\s]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "article";
  return `${safe}.md`;
}

export function downloadMarkdown(filename: string, text: string): void {
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
