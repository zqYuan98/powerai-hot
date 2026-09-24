"use client";
import React, { useCallback, useEffect, useState } from "react";
import { Article } from "../../lib/types";
import { api, mapArticle, ReportDetail, ReportSummary } from "../../lib/api";
import ArticleCard from "../feed/ArticleCard";
import { Spark } from "../icons";

export default function DigestModule({
  favIds, onToggleFav,
}: {

  favIds: Record<number, boolean>; onToggleFav: (a: Article) => void;
}) {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [listLoaded, setListLoaded] = useState(false);

  const loadList = useCallback((isCurrent: () => boolean = () => true) =>
    api.listReports("daily").then((rows) => {
      if (!isCurrent()) return;
      setReports(rows);
      setListLoaded(true);
      setError(null);
      if (rows.length) setActiveId((current) => current ?? rows[0].id);
    }).catch(() => {
      if (!isCurrent()) return;
      setReports([]);
      setDetail(null);
      setActiveId(null);
      setListLoaded(true);
      setError("日报加载失败，请稍后重试");
    }), []);

  useEffect(() => {
    let alive = true;
    loadList(() => alive);
    return () => { alive = false; };
  }, [loadList]);
  useEffect(() => {
    if (activeId == null) return;
    let alive = true;
    setDetail(null);
    api.getReport(activeId).then((d) => {
      if (!alive) return;
      setDetail(d);
      setError(null);
    }).catch(() => {
      if (!alive) return;
      setDetail(null);
      setError("日报详情加载失败，请稍后重试");
    });
    return () => { alive = false; };
  }, [activeId]);

  return (
    <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", position: "relative", zIndex: 1 }}>
      {/* 头部：标题 + 日期切换 */}
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 14, padding: "18px 26px", borderBottom: "1px solid rgba(148,163,184,0.10)", flexShrink: 0 }}>
        <Spark size={18} />
        <span style={{ fontSize: 17, fontWeight: 700, color: "#F2F5FA" }}>今日精选</span>
        <span style={{ fontSize: 12, color: "#6B7689" }}>近 24 小时精选主条 · 按版块分组 · 15 分钟读完</span>
        {detail?.created_at && (
          <span title="每日 07:00 自动生成；后端启动时缺当日报会自动补" style={{ fontSize: 11, color: "#5E6A82", fontFamily: "'JetBrains Mono', monospace" }}>
            生成于 {(() => {
              const d = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(detail.created_at!) ? detail.created_at! : detail.created_at + "Z");
              const p = (n: number) => String(n).padStart(2, "0");
              return isNaN(d.getTime()) ? "—" : `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
            })()}
          </span>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          {reports.slice(0, 7).map((r) => {
            const on = r.id === activeId;
            return (
              <span key={r.id} onClick={() => setActiveId(r.id)}
                style={{ fontSize: 12, fontWeight: on ? 700 : 500, cursor: "pointer", padding: "5px 10px", borderRadius: 8, color: on ? "#0A0E17" : "#94A0B5", background: on ? "linear-gradient(145deg,#34E0D8,#1FB6C9)" : "rgba(148,163,184,0.08)", border: on ? "none" : "1px solid rgba(148,163,184,0.14)" }}>
                {r.title.split("· ")[1] ?? r.title}
              </span>
            );
          })}
        </div>
      </div>

      {/* 正文：版块分组 */}
      <div style={{ flex: 1, overflow: "auto", padding: "18px 26px 26px", display: "flex", flexDirection: "column", gap: 18 }}>
        {!error && detail?.sections.map((sec) => (
          <section key={sec.name}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "6px 0 12px" }}>
              <span style={{ width: 4, height: 16, borderRadius: 2, background: "linear-gradient(180deg,#3B9EFF,#34E0D8)" }} />
              <span style={{ fontSize: 15, fontWeight: 700, color: "#F2F5FA" }}>{sec.name}</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#586074" }}>{sec.articles.length}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {sec.articles.map((raw) => {
                const a = mapArticle(raw);
                return <ArticleCard key={a.id} article={a}
                  favorited={!!favIds[a.id]} onToggleFav={() => onToggleFav(a)} />;
              })}
            </div>
          </section>
        ))}
        {error && <div style={{ color: "#FCA5A5", fontSize: 13.5, padding: "24px 0" }}>{error}</div>}
        {!error && listLoaded && ((!detail && reports.length === 0) || (detail && detail.sections.length === 0)) && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#5E6A82", gap: 12, textAlign: "center", padding: "80px 0" }}>
            <Spark size={32} />
            <div style={{ fontSize: 15, color: "#828EA3" }}>{reports.length === 0 ? "还没有日报" : "该日报暂无内容"}</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.7 }}>每天 07:00 自动生成；如需提前生成，请联系管理员或等待定时任务。</div>
          </div>
        )}
      </div>
    </main>
  );
}
