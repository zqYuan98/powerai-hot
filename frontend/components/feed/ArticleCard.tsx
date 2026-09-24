"use client";
import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Article } from "../../lib/types";
import { api } from "../../lib/api";
import { Spark } from "../icons";

const ACCENT_BAR: Record<NonNullable<Article["accent"]>, string> = {
  blue: "linear-gradient(180deg, #3B9EFF, #1E6FE0)",
  green: "linear-gradient(180deg, #34D399, #10A372)",
  amber: "linear-gradient(180deg, #FBBF24, #F59E0B)",
  violet: "linear-gradient(180deg, #A78BFA, #6D45E8)",
};

// 机构标签配色：按机构名映射到原型中的色板。
function orgTag(org?: string): React.CSSProperties {
  const map: Record<string, [string, string, string]> = {
    国家电网: ["#9FD0FF", "rgba(59,158,255,0.14)", "rgba(59,158,255,0.28)"],
    浙江电力: ["#9FD0FF", "rgba(59,158,255,0.14)", "rgba(59,158,255,0.28)"],
    南方电网: ["#6EE7B7", "rgba(52,211,153,0.14)", "rgba(52,211,153,0.28)"],
    国家能源局: ["#6EE7B7", "rgba(52,211,153,0.14)", "rgba(52,211,153,0.28)"],
    招标公告: ["#FCD34D", "rgba(251,191,36,0.14)", "rgba(251,191,36,0.3)"],
  };
  const [fg, bg, bd] = map[org ?? ""] ?? ["#9FD0FF", "rgba(59,158,255,0.14)", "rgba(59,158,255,0.28)"];
  return { fontSize: 11, fontWeight: 700, color: fg, background: bg, border: `1px solid ${bd}`, padding: "4px 9px", borderRadius: 7 };
}

const softTag: React.CSSProperties = {
  fontSize: 11, fontWeight: 500, color: "#8EE6E0", background: "rgba(52,224,216,0.10)",
  border: "1px solid rgba(52,224,216,0.24)", padding: "4px 9px", borderRadius: 7,
};

// 相关度分（aihot 式热度）：分越高越偏暖色。
function ScoreBadge({ score }: { score: number }) {
  const [fg, bg, bd] =
    score >= 80 ? ["#FCA5A5", "rgba(251,113,133,0.14)", "rgba(251,113,133,0.32)"]
    : score >= 60 ? ["#FCD34D", "rgba(251,191,36,0.14)", "rgba(251,191,36,0.3)"]
    : ["#94A0B5", "rgba(148,163,184,0.1)", "rgba(148,163,184,0.22)"];
  return (
    <span title="AI 相关度评分" style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: fg, background: bg, border: `1px solid ${bd}`, padding: "3px 9px", borderRadius: 7 }}>
      <svg width={11} height={11} viewBox="0 0 24 24" fill={fg}><path d="M12 2l3 6.3 6.9.9-5 4.8 1.2 6.9L12 17.8 5.9 20.9 7.1 14l-5-4.8 6.9-.9z" /></svg>
      {score}
    </span>
  );
}

// 信源分级徽标配色：可信度透明化（T1 官方 / T1.5 重点 / T2 自媒体）
// 双轴徽标：交叉区是本产品的核心价值，给最强的视觉权重；
// 单轴只做弱标注，纯噪音（弱）不显示徽标以免干扰阅读。
const AXIS_STYLE: Record<string, { fg: string; bg: string; bd: string; label: string; title: string }> = {
  "交叉": { fg: "#0A0E17", bg: "linear-gradient(145deg,#FBBF24,#F59E0B)", bd: "transparent",
           label: "交叉", title: "AI 技术轴与电力业务轴同时命中——最值得关注" },
  "AI": { fg: "#B79CFF", bg: "rgba(167,139,250,0.14)", bd: "rgba(167,139,250,0.30)",
          label: "AI", title: "仅 AI 技术轴命中" },
  "行业": { fg: "#8EE6E0", bg: "rgba(52,224,216,0.12)", bd: "rgba(52,224,216,0.30)",
           label: "行业", title: "仅电力业务轴命中" },
};

const TIER_STYLE: Record<string, [string, string]> = {
  T1: ["#6EE7B7", "rgba(52,211,153,0.28)"],
  "T1.5": ["#9FD0FF", "rgba(59,158,255,0.28)"],
  T2: ["#94A0B5", "rgba(148,163,184,0.24)"],
};

export default function ArticleCard({
  article, favorited, onToggleFav, onTagClick, read, onRead,
}: {
  article: Article;
  favorited?: boolean; onToggleFav?: () => void;
  /** 点击标签下钻筛选（信息流内传入；其他场景不传则标签不可点） */
  onTagClick?: (tag: string) => void;
  /** 已读置灰：读过的卡片降透明度、标题转灰（本地状态，信息流传入） */
  read?: boolean;
  onRead?: () => void;
}) {
  const router = useRouter();
  const isPaper = article.kind === "论文";
  const displayTitle = article.meta?.titleZh || article.title;
  const [expanded, setExpanded] = useState(false);
  const [related, setRelated] = useState<any[] | null>(null);
  const toggleCluster = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!expanded && related === null) {
      try { setRelated(await api.getClusterArticles(article.id)); } catch { setRelated([]); }
    }
    setExpanded(!expanded);
  };
  const isAI = article.channel === "AI洞察";
  const isBid = article.channel === "招标公告";
  const cardBg = isAI
    ? "linear-gradient(180deg, rgba(28,22,48,0.9), rgba(18,16,34,0.9))"
    : "linear-gradient(180deg, rgba(20,27,42,0.9), rgba(15,20,32,0.9))";
  const cardBorder = isAI ? "1px solid rgba(167,139,250,0.28)" : isBid ? "1px solid rgba(251,191,36,0.22)" : "1px solid rgba(148,163,184,0.12)";
  const summaryBg = isAI
    ? "linear-gradient(90deg, rgba(167,139,250,0.12), rgba(59,158,255,0.04))"
    : "linear-gradient(90deg, rgba(167,139,250,0.08), rgba(59,158,255,0.04))";
  const summaryBorder = isAI ? "1px solid rgba(167,139,250,0.22)" : "1px solid rgba(167,139,250,0.16)";

  // primary add button = blue/green/amber accents? 原型中 c1、c5 用青色实心强调按钮。

  return (
    <article
      data-read={read || undefined}
      onClick={() => { onRead?.(); router.push(`/items/${article.id}`); }}
      title="查看详情"
      style={{ background: cardBg, border: cardBorder, borderRadius: 16, padding: "20px 22px", position: "relative", overflow: "hidden", flexShrink: 0, cursor: "pointer", transition: "border-color .15s", opacity: read ? 0.62 : undefined }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = "rgba(52,224,216,0.4)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = ""; }}
    >
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: ACCENT_BAR[article.accent ?? "blue"] }} />

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {article.crawledMs !== undefined && Date.now() - article.crawledMs < 24 * 36e5 && (
          <span title="24 小时内新入库" style={{ fontSize: 10.5, fontWeight: 800, color: "#0A0E17", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", padding: "3px 7px", borderRadius: 6, letterSpacing: "0.05em" }}>
            新
          </span>
        )}
        {article.axis && AXIS_STYLE[article.axis] && (
          <span
            title={`${AXIS_STYLE[article.axis].title}${article.crossScore !== undefined ? `（交叉分 ${article.crossScore}）` : ""}`}
            style={{ fontSize: 10.5, fontWeight: 800, color: AXIS_STYLE[article.axis].fg, background: AXIS_STYLE[article.axis].bg, border: `1px solid ${AXIS_STYLE[article.axis].bd}`, padding: "3px 8px", borderRadius: 6, letterSpacing: "0.04em" }}
          >
            {AXIS_STYLE[article.axis].label}
          </span>
        )}
        {isAI ? (
          <span style={{ fontSize: 11, fontWeight: 700, color: "#B79CFF", background: "rgba(167,139,250,0.16)", border: "1px solid rgba(167,139,250,0.34)", padding: "4px 9px", borderRadius: 7, display: "flex", alignItems: "center", gap: 5 }}>
            <Spark size={12} />AI 洞察
          </span>
        ) : (
          <span style={orgTag(article.org)}>{article.org}</span>
        )}
        {article.tags.map((t, i) => (
          <span
            key={i}
            title={onTagClick ? `筛选标签「${t}」` : undefined}
            onClick={onTagClick ? (e) => { e.stopPropagation(); onTagClick(t); } : undefined}
            style={{
              ...(i % 2 === 0 ? softTag : { ...softTag, color: "#B79CFF", background: "rgba(167,139,250,0.10)", border: "1px solid rgba(167,139,250,0.22)" }),
              cursor: onTagClick ? "pointer" : undefined,
            }}
          >
            {t}
          </span>
        ))}

        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          {isBid && article.deadlineDays != null && (
            <span style={{ fontSize: 12, color: "#FB7185", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FB7185", boxShadow: "0 0 8px #FB7185" }} />距截止 {article.deadlineDays} 天
            </span>
          )}
          {article.noiseReason && (
            <span title="预筛打回原因" style={{ fontSize: 11, color: "#828EA3", background: "rgba(148,163,184,0.10)", border: "1px solid rgba(148,163,184,0.2)", padding: "3px 9px", borderRadius: 7 }}>
              {article.noiseReason}
            </span>
          )}
          {article.scoredBy && article.scoredBy !== "primary_model" && (
            <span title="分析降级来源" style={{ fontSize: 11, color: article.scoredBy === "rule" ? "#FCD34D" : "#9FD0FF", background: article.scoredBy === "rule" ? "rgba(251,191,36,0.12)" : "rgba(59,158,255,0.10)", border: article.scoredBy === "rule" ? "1px solid rgba(251,191,36,0.28)" : "1px solid rgba(59,158,255,0.24)", padding: "3px 9px", borderRadius: 7 }}>
              {article.scoredBy === "rule" ? "规则评分" : article.scoredBy === "fallback_model" ? "备用模型" : article.processingStatus ?? "未评分"}
            </span>
          )}
          {article.hot && (
            <span style={{ fontSize: 12, color: "#FBBF24", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FBBF24", boxShadow: "0 0 8px #FBBF24" }} />热点
            </span>
          )}
          {typeof article.relevanceScore === "number" && <ScoreBadge score={article.relevanceScore} />}
        </span>
      </div>

      <h3 style={{ margin: "0 0 11px", fontSize: 18, fontWeight: 700, lineHeight: 1.4, color: read ? "#8A94A8" : "#F2F5FA" }}>{displayTitle}</h3>
      {isPaper && article.meta?.titleZh && (
        <div style={{ margin: "-6px 0 11px", fontSize: 12.5, color: "#828EA3", lineHeight: 1.5 }}>{article.title}</div>
      )}
      {isPaper && article.meta && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 11, fontSize: 12, color: "#94A0B5" }}>
          {article.meta.authors?.length ? (
            <span>{article.meta.authors.slice(0, 4).join(" · ")}{article.meta.authors.length > 4 ? " 等" : ""}</span>
          ) : null}
          {[
            article.meta.arxivId && { label: "arXiv", href: `https://arxiv.org/abs/${article.meta.arxivId}` },
            article.meta.pdfUrl && { label: "PDF", href: article.meta.pdfUrl },
            article.meta.hfUrl && { label: "HF", href: article.meta.hfUrl },
          ].filter(Boolean).map((l: any) => (
            <a key={l.label} href={l.href} target="_blank" rel="noreferrer"
               onClick={(e) => e.stopPropagation()}
               style={{ fontSize: 11, fontWeight: 700, color: "#9FD0FF", background: "rgba(59,158,255,0.10)", border: "1px solid rgba(59,158,255,0.24)", padding: "3px 9px", borderRadius: 7, textDecoration: "none" }}>
              {l.label} ↗
            </a>
          ))}
        </div>
      )}

      <div style={{ background: summaryBg, border: summaryBorder, borderRadius: 11, padding: "12px 14px", display: "flex", gap: 11 }}>
        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 5, height: 20 }}>
          <Spark size={14} style={{ animation: "pAIglow 2.4s ease-in-out infinite" }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: "#B79CFF", fontFamily: "'Space Grotesk', sans-serif" }}>{isAI ? "AI 综合分析" : "AI 摘要"}</span>
        </div>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "#C4CDDD" }}>{article.summary}</p>
      </div>

      {article.curated && !article.noiseReason && article.recommendReason && (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 7, marginTop: 10, padding: "9px 12px", background: "rgba(52,224,216,0.05)", border: "1px solid rgba(52,224,216,0.16)", borderLeft: "3px solid #34E0D8", borderRadius: 9 }}>
          <span style={{ flexShrink: 0, fontSize: 11, fontWeight: 700, color: "#8EE6E0", marginTop: 1 }}>推荐理由</span>
          <span style={{ fontSize: 12.5, lineHeight: 1.6, color: "#A9D8D3" }}>{article.recommendReason}</span>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 14 }}>
        <span title={article.publishedLabel} style={{ fontSize: 12, color: "#6B7689" }}>
          {article.timeLabel ?? article.publishedLabel}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: "#6B7689", fontFamily: "'JetBrains Mono', monospace" }}>{article.sourceDomain}</span>
          {article.tier && (
            <span
              title={article.tier === "T1" ? "T1 官方信源" : article.tier === "T1.5" ? "T1.5 重点信源" : "T2 自媒体信源"}
              style={{
                fontSize: 10, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                color: (TIER_STYLE[article.tier] ?? TIER_STYLE.T2)[0],
                border: `1px solid ${(TIER_STYLE[article.tier] ?? TIER_STYLE.T2)[1]}`,
                padding: "1px 6px", borderRadius: 6,
              }}
            >
              {article.tier}
            </span>
          )}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#9FD0FF" }}>
          查看详情
          <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M9 6l6 6-6 6" /></svg>
        </span>
        {(article.relatedCount ?? 0) > 0 && (
          <span onClick={toggleCluster}
            style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#8EE6E0", cursor: "pointer" }}>
            {article.relatedCount} 条相关报道
            <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
              style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .15s" }}>
              <path d="M6 9l6 6 6-6" />
            </svg>
          </span>
        )}
        {/* 收藏星标：承载右侧按钮组的 marginLeft:auto——若复用本组件且不传 onToggleFav，需把 auto 移回需求池按钮 */}
        {onToggleFav && (
          <button onClick={(e) => { e.stopPropagation(); onToggleFav(); }}
            title={favorited ? "取消收藏" : "收藏到我的知识库"}
            style={{ marginLeft: "auto", display: "flex", alignItems: "center", justifyContent: "center", width: 36, height: 36, borderRadius: 9, cursor: "pointer", background: favorited ? "rgba(251,191,36,0.14)" : "rgba(148,163,184,0.08)", border: favorited ? "1px solid rgba(251,191,36,0.35)" : "1px solid rgba(148,163,184,0.18)" }}>
            <svg width={16} height={16} viewBox="0 0 24 24" fill={favorited ? "#FBBF24" : "none"} stroke={favorited ? "#FBBF24" : "#94A0B5"} strokeWidth={1.8}>
              <path d="M12 2l3 6.3 6.9.9-5 4.8 1.2 6.9L12 17.8 5.9 20.9 7.1 14l-5-4.8 6.9-.9z" />
            </svg>
          </button>
        )}
      </div>

      {expanded && related && (
        <div style={{ marginTop: 12, padding: "10px 12px", background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          {related.filter((r) => r.id !== article.id).map((r) => (
            <a key={r.id} href={r.url ?? "#"} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
              style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5, color: "#C4CDDD", textDecoration: "none" }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#586074", flexShrink: 0 }} />
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</span>
              <span style={{ marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#586074", flexShrink: 0 }}>{r.source_domain}</span>
            </a>
          ))}
        </div>
      )}
    </article>
  );
}
