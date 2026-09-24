"use client";
import React, { useEffect, useState } from "react";
import { api, ReportDetail, ReportSummary } from "../../lib/api";
import { useIsMobile } from "../../lib/useViewport";
import { Doc } from "../icons";

/** 链接 scheme 白名单：素材来自抓取的文章标题/摘要，可能含 javascript: 等注入向量，
 *  只放行 http/https/mailto，其余降级为纯文本，防存储型 XSS。 */
function safeHref(url: string): string | null {
  return /^(https?:|mailto:)/i.test(url.trim()) ? url : null;
}

/** 迷你 markdown 渲染：标题/列表/粗体/链接/段落，不引第三方依赖。 */
function renderInline(text: string, key: number): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let rest = text, i = 0;
  const re = /\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)]+)\)/;
  while (rest) {
    const m = rest.match(re);
    if (!m || m.index === undefined) { parts.push(rest); break; }
    if (m.index > 0) parts.push(rest.slice(0, m.index));
    if (m[1] !== undefined) {
      parts.push(<strong key={`${key}-${i}`} style={{ color: "#F2F5FA" }}>{m[1]}</strong>);
    } else {
      const href = safeHref(m[3]);
      parts.push(href
        ? <a key={`${key}-${i}`} href={href} target="_blank" rel="noreferrer" style={{ color: "#9FD0FF" }}>{m[2]}</a>
        : <span key={`${key}-${i}`}>{m[2]}</span>);
    }
    rest = rest.slice(m.index + m[0].length);
    i += 1;
  }
  return parts;
}

function Markdown({ md }: { md: string }) {
  const blocks: React.ReactNode[] = [];
  let list: React.ReactNode[] = [];
  const flush = (k: string) => {
    if (list.length) { blocks.push(<ul key={k} style={{ margin: "6px 0 12px", paddingLeft: 22, display: "flex", flexDirection: "column", gap: 6 }}>{list}</ul>); list = []; }
  };
  md.split(/\r?\n/).forEach((line, n) => {
    const t = line.trim();
    if (t.startsWith("- ")) { list.push(<li key={n} style={{ fontSize: 13.5, lineHeight: 1.7, color: "#C4CDDD" }}>{renderInline(t.slice(2), n)}</li>); return; }
    flush(`ul-${n}`);
    if (!t) return;
    if (t.startsWith("### ")) blocks.push(<h4 key={n} style={{ margin: "14px 0 6px", fontSize: 14, color: "#DCE3EF" }}>{renderInline(t.slice(4), n)}</h4>);
    else if (t.startsWith("## ")) blocks.push(<h3 key={n} style={{ margin: "18px 0 8px", fontSize: 16, color: "#F2F5FA", display: "flex", alignItems: "center", gap: 8 }}><span style={{ width: 4, height: 15, borderRadius: 2, background: "linear-gradient(180deg,#3B9EFF,#34E0D8)" }} />{renderInline(t.slice(3), n)}</h3>);
    else if (t.startsWith("# ")) blocks.push(<h2 key={n} style={{ margin: "6px 0 10px", fontSize: 18, color: "#F2F5FA" }}>{renderInline(t.slice(2), n)}</h2>);
    else blocks.push(<p key={n} style={{ margin: "0 0 10px", fontSize: 13.5, lineHeight: 1.75, color: "#C4CDDD" }}>{renderInline(t, n)}</p>);
  });
  flush("ul-end");
  return <div>{blocks}</div>;
}

const TYPE_LABEL: Record<string, string> = { weekly: "周报", topic: "研报", daily: "日报" };

export default function ResearchModule() {
  const isMobile = useIsMobile();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadList = async (isCurrent: () => boolean = () => true) => {
    try {
      const all = await api.listReports();
      const rows = all.filter((r) => r.type !== "daily");
      if (!isCurrent()) return rows;
      setReports(rows);
      setError(null);
      return rows;
    } catch {
      if (!isCurrent()) return [] as ReportSummary[];
      setReports([]);
      setError("报告列表加载失败，请稍后重试");
      return [] as ReportSummary[];
    }
  };

  useEffect(() => {
    let alive = true;
    loadList(() => alive).then((rows) => { if (alive && rows.length) setActiveId(rows[0].id); });
    return () => { alive = false; };
  }, []);

  // 详情加载 + 生成中轮询（3s）
  useEffect(() => {
    if (activeId == null) { setDetail(null); return; }
    setDetail(null);
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let inFlight = false;
    const fetchDetail = async () => {
      if (!alive || inFlight) return;
      inFlight = true;
      try {
        const d = await api.getReport(activeId);
        if (!alive) return;
        setDetail(d);
        setError(null);
        if (alive && d.status === "生成中") timer = setTimeout(fetchDetail, 3000);
        if (alive && d.status !== "生成中") loadList(() => alive);
      } catch {
        if (!alive) return;
        setDetail(null);
        setError("报告详情加载失败，请稍后重试");
        timer = setTimeout(fetchDetail, 3000);
      } finally {
        inFlight = false;
      }
    };
    fetchDetail();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [activeId]);

  return (
    <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", position: "relative", zIndex: 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "18px 26px", borderBottom: "1px solid rgba(148,163,184,0.10)", flexShrink: 0 }}>
        <Doc />
        <span style={{ fontSize: 17, fontWeight: 700, color: "#F2F5FA" }}>研报</span>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#6B7689" }}>内容由管理员发起，员工可在此阅读</span>
      </div>

      <div style={{ flex: 1, display: "flex", flexDirection: isMobile ? "column" : "row", minHeight: 0 }}>
        {/* 左列：报告列表（移动端置顶收窄，正文在下方） */}
        <div style={{ width: isMobile ? "100%" : 280, maxHeight: isMobile ? 180 : undefined, flexShrink: 0, borderRight: isMobile ? "none" : "1px solid rgba(148,163,184,0.10)", borderBottom: isMobile ? "1px solid rgba(148,163,184,0.10)" : "none", overflow: "auto", padding: "14px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
          {reports.map((r) => {
            const on = r.id === activeId;
            const [fg, bg] = r.status === "完成" ? ["#6EE7B7", "rgba(52,211,153,0.12)"]
              : r.status === "失败" ? ["#FCA5A5", "rgba(251,113,133,0.12)"] : ["#FCD34D", "rgba(251,191,36,0.12)"];
            return (
              <div key={r.id} onClick={() => setActiveId(r.id)}
                style={{ padding: "10px 12px", borderRadius: 10, cursor: "pointer", background: on ? "rgba(59,158,255,0.10)" : "transparent", border: on ? "1px solid rgba(59,158,255,0.25)" : "1px solid transparent" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#B79CFF", background: "rgba(167,139,250,0.14)", padding: "2px 7px", borderRadius: 6 }}>{TYPE_LABEL[r.type] ?? r.type}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: fg, background: bg, padding: "2px 7px", borderRadius: 6 }}>{r.status}</span>
                </div>
                <div style={{ fontSize: 13, fontWeight: on ? 700 : 500, color: on ? "#F2F5FA" : "#B7C0D2", lineHeight: 1.45, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</div>
              </div>
            );
          })}
          {reports.length === 0 && <div style={{ fontSize: 12.5, color: "#5E6A82", padding: 12, lineHeight: 1.7 }}>还没有周报/研报，请联系管理员或等待定时生成。</div>}
        </div>

        {/* 右侧：详情 */}
        <div style={{ flex: 1, overflow: "auto", padding: isMobile ? "16px 14px" : "20px 30px" }}>
          {detail?.status === "生成中" && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#FCD34D", fontSize: 13.5, padding: "40px 0" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#FCD34D", boxShadow: "0 0 10px #FCD34D", animation: "pAIglow 1.2s ease-in-out infinite" }} />
              正在检索素材并撰写，通常需要 20-60 秒，页面会自动刷新…
            </div>
          )}
          {error && (
            <div style={{ color: "#FCA5A5", fontSize: 13.5, padding: "24px 0" }}>{error}</div>
          )}
          {detail?.status === "失败" && (
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "40px 0" }}>
              <span style={{ fontSize: 13.5, color: "#FCA5A5" }}>生成失败，请联系管理员处理。</span>
            </div>
          )}
          {detail?.status === "完成" && detail.content_md && (
            <>
              <h2 style={{ margin: "0 0 4px", fontSize: 19, color: "#F2F5FA" }}>{detail.title}</h2>
              <div style={{ fontSize: 11.5, color: "#5E6A82", marginBottom: 16 }}>{detail.created_at?.slice(0, 16).replace("T", " ")}</div>
              <Markdown md={detail.content_md} />
            </>
          )}
          {!error && !detail && <div style={{ color: "#5E6A82", fontSize: 13.5, padding: "40px 0" }}>选择左侧报告查看内容。</div>}
        </div>
      </div>
    </main>
  );
}
