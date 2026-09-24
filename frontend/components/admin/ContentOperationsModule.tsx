"use client";

import React, { useCallback, useEffect, useState } from "react";
import { api, CardOut, ReportSummary } from "../../lib/api";
import { Doc } from "../icons";

type Feedback = { kind: "success" | "error"; message: string };

const panel: React.CSSProperties = {
  background: "linear-gradient(180deg, rgba(20,27,42,0.92), rgba(15,20,32,0.92))",
  border: "1px solid rgba(148,163,184,0.13)", borderRadius: 14, padding: "20px 22px",
};

export default function ContentOperationsModule() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [cards, setCards] = useState<CardOut[]>([]);
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState<Record<string, Feedback | undefined>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [reportResult, cardResult] = await Promise.allSettled([api.listReports(), api.listCards()]);
    if (reportResult.status === "fulfilled") setReports(reportResult.value);
    if (cardResult.status === "fulfilled") setCards(cardResult.value);
    if (reportResult.status === "rejected" || cardResult.status === "rejected") setLoadError("内容列表加载失败，请稍后重试");
    else setLoadError(null);
  }, []);

  useEffect(() => { load(); }, [load]);

  const run = async (key: string, task: () => Promise<unknown>, success: string): Promise<boolean> => {
    if (busy[key]) return false;
    setBusy((current) => ({ ...current, [key]: true }));
    setFeedback((current) => ({ ...current, [key]: undefined }));
    try {
      await task();
      setFeedback((current) => ({ ...current, [key]: { kind: "success", message: success } }));
      await load();
      return true;
    } catch {
      setFeedback((current) => ({ ...current, [key]: { kind: "error", message: "操作失败，请检查后端连接或查看日志" } }));
      return false;
    } finally {
      setBusy((current) => ({ ...current, [key]: false }));
    }
  };

  const runDigest = () => run("digest", () => api.digestNow(), "已提交日报生成任务");
  const runWeekly = () => run("weekly", () => api.weeklyNow(), "已提交周报生成任务");
  const runTopic = () => {
    const value = topic.trim();
    if (!value) return;
    return run("topic", () => api.createTopicReport(value), "已提交主题研报任务").then((succeeded) => { if (succeeded) setTopic(""); });
  };

  const failedReports = reports.filter((report) => report.status === "失败" && report.type !== "daily");
  const failedCards = cards.filter((card) => card.status === "失败");

  return (
    <main style={{ flex: 1, minWidth: 0, overflow: "auto", padding: "26px 30px 38px", position: "relative", zIndex: 1 }}>
      <div style={{ maxWidth: 1120, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
        <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Doc />
          <div>
            <h1 style={{ margin: 0, fontSize: 21, color: "#F2F5FA" }}>内容运营</h1>
            <p style={{ margin: "5px 0 0", fontSize: 12.5, color: "#7E8AA1" }}>日报、周报、主题研报和失败任务均在此发起或重试</p>
          </div>
        </header>

        <section style={panel} aria-labelledby="content-generate-heading">
          <h2 id="content-generate-heading" style={{ margin: "0 0 14px", fontSize: 15, color: "#DCE3EF" }}>生成任务</h2>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" onClick={runDigest} disabled={!!busy.digest} style={{ fontSize: 12.5, fontWeight: 700, color: "#0A0E17", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", border: "none", padding: "9px 15px", borderRadius: 9, cursor: busy.digest ? "wait" : "pointer", opacity: busy.digest ? 0.55 : 1 }}>
              {busy.digest ? "执行中…" : "立即生成日报"}
            </button>
            <button type="button" onClick={runWeekly} disabled={!!busy.weekly} style={{ fontSize: 12.5, fontWeight: 600, color: "#9FD0FF", background: "rgba(59,158,255,0.12)", border: "1px solid rgba(59,158,255,0.22)", padding: "8px 14px", borderRadius: 9, cursor: busy.weekly ? "wait" : "pointer", opacity: busy.weekly ? 0.55 : 1 }}>
              {busy.weekly ? "执行中…" : "生成本周周报"}
            </button>
            <input value={topic} onChange={(event) => setTopic(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") runTopic(); }} placeholder="输入主题" style={{ minWidth: 220, flex: 1, fontSize: 13, color: "#E6EBF4", background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.14)", borderRadius: 9, padding: "9px 12px" }} />
            <button type="button" onClick={runTopic} disabled={!!busy.topic || !topic.trim()} style={{ fontSize: 12.5, fontWeight: 600, color: "#D8CBFF", background: "rgba(167,139,250,0.14)", border: "1px solid rgba(167,139,250,0.28)", padding: "8px 14px", borderRadius: 9, cursor: busy.topic ? "wait" : "pointer", opacity: busy.topic || !topic.trim() ? 0.55 : 1 }}>
              {busy.topic ? "执行中…" : "发起主题研报"}
            </button>
          </div>
          <FeedbackView feedback={feedback.digest} />
          <FeedbackView feedback={feedback.weekly} />
          <FeedbackView feedback={feedback.topic} />
        </section>

        <section style={panel} aria-labelledby="content-retry-heading">
          <h2 id="content-retry-heading" style={{ margin: "0 0 14px", fontSize: 15, color: "#DCE3EF" }}>失败任务</h2>
          {loadError && <div style={{ color: "#FCA5A5", fontSize: 13, marginBottom: 10 }}>{loadError}</div>}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12 }}>
            <div>
              <div style={{ fontSize: 11.5, color: "#8EA0C0", marginBottom: 8 }}>报告</div>
              {failedReports.length === 0 ? <div style={{ color: "#5E6A82", fontSize: 12.5 }}>暂无失败报告</div> : failedReports.map((report) => {
                const key = `report-${report.id}`;
                return <div key={report.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 10px", marginBottom: 6, borderRadius: 9, background: "rgba(251,113,133,0.06)" }}>
                  <span style={{ flex: 1, color: "#C4CDDD", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{report.title}</span>
                  <button type="button" aria-label={`重试报告：${report.title}`} onClick={() => run(key, () => api.retryReport(report.id), "已提交报告重试任务")} disabled={!!busy[key]} style={{ fontSize: 11.5, color: "#9FD0FF", background: "rgba(59,158,255,0.12)", border: "1px solid rgba(59,158,255,0.22)", padding: "5px 9px", borderRadius: 7, cursor: busy[key] ? "wait" : "pointer", opacity: busy[key] ? 0.55 : 1 }}>{busy[key] ? "执行中…" : "重试"}</button>
                  <FeedbackView feedback={feedback[key]} inline />
                </div>;
              })}
            </div>
            <div>
              <div style={{ fontSize: 11.5, color: "#8EA0C0", marginBottom: 8 }}>知识卡片</div>
              {failedCards.length === 0 ? <div style={{ color: "#5E6A82", fontSize: 12.5 }}>暂无失败卡片</div> : failedCards.map((card) => {
                const key = `card-${card.id}`;
                const title = card.article?.title_zh || card.article?.title || `#${card.article_id}`;
                return <div key={card.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 10px", marginBottom: 6, borderRadius: 9, background: "rgba(251,113,133,0.06)" }}>
                  <span style={{ flex: 1, color: "#C4CDDD", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</span>
                  <button type="button" aria-label={`重试卡片：${title}`} onClick={() => run(key, () => api.retryCard(card.id), "已提交卡片重试任务")} disabled={!!busy[key]} style={{ fontSize: 11.5, color: "#9FD0FF", background: "rgba(59,158,255,0.12)", border: "1px solid rgba(59,158,255,0.22)", padding: "5px 9px", borderRadius: 7, cursor: busy[key] ? "wait" : "pointer", opacity: busy[key] ? 0.55 : 1 }}>{busy[key] ? "执行中…" : "重试"}</button>
                  <FeedbackView feedback={feedback[key]} inline />
                </div>;
              })}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function FeedbackView({ feedback, inline = false }: { feedback?: Feedback; inline?: boolean }) {
  if (!feedback) return null;
  return <span style={{ display: inline ? "inline" : "block", marginTop: inline ? 0 : 8, fontSize: 11.5, color: feedback.kind === "success" ? "#6EE7B7" : "#FCA5A5" }}>{feedback.message}</span>;
}
