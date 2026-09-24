"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, mapArticle } from "../../../lib/api";
import { buildArticleMarkdown, downloadMarkdown, markdownFilename } from "../../../lib/markdownExport";
import { markRead } from "../../../lib/readStore";
import { Article } from "../../../lib/types";

const PAGE_BG: React.CSSProperties = {
  minHeight: "100vh",
  background: "#0A0C12",
  backgroundImage:
    "radial-gradient(900px 500px at 12% -8%, rgba(59,158,255,0.10), transparent 60%), radial-gradient(800px 520px at 98% 4%, rgba(167,139,250,0.10), transparent 60%)",
  color: "#E6EBF4",
  fontFamily: "'Noto Sans SC', sans-serif",
};

function ScorePill({ score }: { score: number }) {
  const [fg, bg, bd] =
    score >= 80 ? ["#FCA5A5", "rgba(251,113,133,0.14)", "rgba(251,113,133,0.32)"]
    : score >= 60 ? ["#FCD34D", "rgba(251,191,36,0.14)", "rgba(251,191,36,0.3)"]
    : ["#94A0B5", "rgba(148,163,184,0.1)", "rgba(148,163,184,0.22)"];
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: fg, background: bg, border: `1px solid ${bd}`, padding: "5px 12px", borderRadius: 8 }}>
      <svg width={13} height={13} viewBox="0 0 24 24" fill={fg}><path d="M12 2l3 6.3 6.9.9-5 4.8 1.2 6.9L12 17.8 5.9 20.9 7.1 14l-5-4.8 6.9-.9z" /></svg>
      相关度 {score}
    </span>
  );
}

export default function ItemPage() {
  const params = useParams<{ id: string }>();
  const [a, setA] = useState<Article | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    api.getArticle(params.id).then((d) => setA(mapArticle(d))).catch(() => setErr(true));
    const id = Number(params.id);
    if (Number.isFinite(id)) markRead(id);  // 进入详情即记已读，返回后信息流卡片置灰
  }, [params.id]);

  return (
    <div style={PAGE_BG}>
      <div style={{ maxWidth: 820, margin: "0 auto", padding: "28px 24px 60px" }}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: "#9FD0FF", textDecoration: "none", marginBottom: 24 }}>
          <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M15 18l-6-6 6-6" /></svg>
          返回情报信息流
        </Link>

        {err && <div style={{ color: "#FB7185", fontSize: 14 }}>未找到该情报，或后端未连接。</div>}
        {!err && !a && <div style={{ color: "#6B7689", fontSize: 14 }}>加载中…</div>}

        {a && (
          <article>
            {/* 标签行 */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
              {a.org && <span style={{ fontSize: 12, fontWeight: 700, color: "#9FD0FF", background: "rgba(59,158,255,0.14)", border: "1px solid rgba(59,158,255,0.28)", padding: "4px 10px", borderRadius: 7 }}>{a.org}</span>}
              <span style={{ fontSize: 12, fontWeight: 500, color: "#8EE6E0", background: "rgba(52,224,216,0.10)", border: "1px solid rgba(52,224,216,0.24)", padding: "4px 10px", borderRadius: 7 }}>{a.channel}</span>
              {typeof a.relevanceScore === "number" && <ScorePill score={a.relevanceScore} />}
              {a.curated && <span style={{ fontSize: 12, fontWeight: 600, color: "#6EE7B7", background: "rgba(52,211,153,0.12)", border: "1px solid rgba(52,211,153,0.3)", padding: "4px 10px", borderRadius: 7 }}>精选</span>}
            </div>

            <h1 style={{ margin: "0 0 12px", fontSize: 26, fontWeight: 800, lineHeight: 1.4, color: "#F4F7FB" }}>{a.title}</h1>
            <div style={{ display: "flex", gap: 16, fontSize: 12.5, color: "#6B7689", marginBottom: 26 }}>
              {a.publishedLabel && <span>{a.publishedLabel}</span>}
              {a.sourceDomain && <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{a.sourceDomain}</span>}
            </div>

            {/* AI 摘要 */}
            {a.summary && (
              <section style={{ background: "linear-gradient(90deg, rgba(167,139,250,0.10), rgba(59,158,255,0.04))", border: "1px solid rgba(167,139,250,0.22)", borderRadius: 12, padding: "16px 18px", marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#B79CFF", marginBottom: 8, fontFamily: "'Space Grotesk', sans-serif" }}>AI 摘要</div>
                <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.8, color: "#C4CDDD" }}>{a.summary}</p>
              </section>
            )}

            {/* 推荐理由 */}
            {a.recommendReason && (
              <section style={{ background: "rgba(52,224,216,0.05)", border: "1px solid rgba(52,224,216,0.18)", borderLeft: "3px solid #34E0D8", borderRadius: 10, padding: "14px 18px", marginBottom: 26 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#8EE6E0", marginBottom: 6 }}>推荐理由</div>
                <p style={{ margin: 0, fontSize: 14, lineHeight: 1.75, color: "#A9D8D3" }}>{a.recommendReason}</p>
              </section>
            )}

            {/* 全文（站内阅读；服务端已白名单消毒） */}
            {a.contentHtml && (
              <section style={{ marginBottom: 26 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#8EA0C0", marginBottom: 10, fontFamily: "'Space Grotesk', sans-serif" }}>全文</div>
                <div className="pai-rich" dangerouslySetInnerHTML={{ __html: a.contentHtml }} />
              </section>
            )}

            {/* 操作区：阅读原文 + 导出 Markdown */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              {a.url && (
                <a href={a.url} target="_blank" rel="noopener noreferrer"
                  style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 700, color: "#0A0E17", background: "linear-gradient(145deg, #34E0D8, #1FB6C9)", border: "none", padding: "12px 22px", borderRadius: 11, cursor: "pointer", textDecoration: "none", boxShadow: "0 8px 22px -8px rgba(52,224,216,0.6)" }}>
                  阅读原文
                  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="#0A0E17" strokeWidth={2.2}><path d="M7 17 17 7M9 7h8v8" /></svg>
                </a>
              )}
              <button type="button"
                onClick={() => downloadMarkdown(markdownFilename(a.meta?.titleZh || a.title), buildArticleMarkdown(a, window.location.origin))}
                style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 700, color: "#9FD0FF", background: "rgba(59,158,255,0.10)", border: "1px solid rgba(59,158,255,0.28)", padding: "12px 22px", borderRadius: 11, cursor: "pointer" }}>
                导出 Markdown
                <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}><path d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14" /></svg>
              </button>
            </div>
            <p style={{ marginTop: 16, fontSize: 12, color: "#5E6A82", lineHeight: 1.7 }}>
              注：摘要、标签、相关度与推荐理由由 AI 生成；正文供站内研读，版权归原作者与原平台，完整内容以原文为准。
            </p>
          </article>
        )}
      </div>
    </div>
  );
}
