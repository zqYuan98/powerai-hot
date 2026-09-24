"use client";

import React, { useEffect, useState } from "react";

import { api, mapArticle } from "../../lib/api";
import type { Article } from "../../lib/types";
import { Bell, Mail, Plus, Triangle, X } from "../icons";
import Toggle from "./Toggle";

export interface Sub {
  keywords: string[];
  notify_in_app: boolean;
  notify_bid_deadline: boolean;
  notify_email_digest: boolean;
}

export default function SubscribeModule({
  sub,
  subDown,
  onSave,
}: {
  sub: Sub | null;
  subDown: boolean;
  onSave: (make: (current: Sub) => Partial<Sub>) => void;
}) {
  const keywords = sub?.keywords ?? [];
  const keywordKey = keywords.join("\u0000");
  const [draft, setDraft] = useState("");
  const [hits, setHits] = useState<Array<{ article: Article; keyword: string }>>([]);

  useEffect(() => {
    if (keywords.length === 0) {
      setHits([]);
      return;
    }
    let active = true;
    api.subscriptionHits(3)
      .then((rows) => {
        if (active) setHits(rows.map((row) => ({ article: mapArticle(row.article), keyword: row.keyword })));
      })
      .catch(() => { if (active) setHits([]); });
    return () => { active = false; };
  }, [keywordKey, keywords.length]);

  const removeKeyword = (keyword: string) => onSave((current) => ({ keywords: current.keywords.filter((item) => item !== keyword) }));
  const addKeyword = () => {
    const value = draft.trim();
    setDraft("");
    if (!value) return;
    onSave((current) => current.keywords.includes(value) ? {} : { keywords: [...current.keywords, value] });
  };

  const toggles = [
    { key: "notify_in_app" as const, icon: <Bell color="#3B9EFF" />, title: "站内消息通知", desc: "命中关键词即时提醒", onColor: "linear-gradient(90deg,#3B9EFF,#34E0D8)" },
    { key: "notify_bid_deadline" as const, icon: <Triangle />, title: "招标截止提醒", desc: "距截止日期较近时自动提醒", onColor: "linear-gradient(90deg,#FBBF24,#F59E0B)" },
    { key: "notify_email_digest" as const, icon: <Mail />, title: "每日邮件摘要", desc: "汇总当日命中内容", onColor: "linear-gradient(90deg,#3B9EFF,#34E0D8)" },
  ];

  return (
    <div style={{ flex: 1, minWidth: 0, overflow: "auto", padding: "28px 30px", position: "relative", zIndex: 1 }}>
      <div style={{ maxWidth: 900 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 22, fontWeight: 900, color: "#F4F7FB" }}>推送订阅</h2>
        <p style={{ margin: "0 0 24px", fontSize: 13, color: "#828EA3" }}>命中订阅关键词的新内容将通过站内消息实时提醒</p>

        <div style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD", marginBottom: 12 }}>关键词订阅</div>
        {sub === null ? (
          <div style={{ fontSize: 12.5, color: "#828EA3", marginBottom: 30, padding: "12px 16px", borderRadius: 11, background: subDown ? "rgba(251,113,133,0.08)" : "rgba(148,163,184,0.05)", border: `1px solid ${subDown ? "rgba(251,113,133,0.28)" : "rgba(148,163,184,0.12)"}` }}>
            {subDown ? "后端未连接，订阅设置暂不可用。" : "正在加载订阅设置…"}
          </div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 9, marginBottom: 30 }}>
            {keywords.map((keyword) => <span key={keyword} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13, color: "#9FD0FF", background: "rgba(59,158,255,0.12)", border: "1px solid rgba(59,158,255,0.26)", padding: "7px 11px", borderRadius: 20 }}>{keyword}<X onClick={() => removeKeyword(keyword)} /></span>)}
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#6B7689", background: "rgba(148,163,184,0.06)", border: "1px dashed rgba(148,163,184,0.28)", padding: "7px 12px", borderRadius: 20 }}>
              <Plus size={13} color="#6B7689" />
              <input value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addKeyword(); }} placeholder="添加关键词，回车确认" style={{ width: 128, background: "transparent", border: "none", outline: "none", color: "#C4CDDD", fontSize: 13 }} />
            </span>
          </div>
        )}

        <div style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD", marginBottom: 12 }}>通知设置</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 30 }}>
          {toggles.map((toggle) => <div key={toggle.key} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", borderRadius: 12, opacity: sub === null ? 0.5 : 1, background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.12)" }}>
            {toggle.icon}<div style={{ flex: 1 }}><div style={{ fontSize: 14, fontWeight: 600, color: "#DCE3EF" }}>{toggle.title}</div><div style={{ fontSize: 11, color: "#6B7689", marginTop: 2 }}>{toggle.desc}</div></div>
            <Toggle on={!!sub?.[toggle.key]} onColor={toggle.onColor} onToggle={() => { if (sub) onSave((current) => ({ [toggle.key]: !current[toggle.key] })); }} />
          </div>)}
        </div>

        <div style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD", marginBottom: 12 }}>最近命中</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {hits.length === 0 && <div style={{ fontSize: 12.5, color: "#5E6A82", padding: "13px 15px", background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 12 }}>{keywords.length === 0 ? "尚未订阅关键词——添加后，命中的新情报会显示在这里。" : "近期内容中暂无命中订阅关键词的条目。"}</div>}
          {hits.map(({ article, keyword }) => <div key={article.id} style={{ display: "flex", gap: 12, padding: "13px 15px", background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 12 }}>
            <div style={{ flexShrink: 0, width: 8, height: 8, borderRadius: "50%", background: "#3B9EFF", marginTop: 5 }} />
            <div style={{ minWidth: 0 }}><div style={{ fontSize: 13.5, color: "#C4CDDD", lineHeight: 1.5 }}>{article.meta?.titleZh || article.title}</div><div style={{ fontSize: 11, color: "#6B7689", marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>命中：{keyword}{article.publishedLabel ? ` · ${article.publishedLabel}` : ""}</div></div>
          </div>)}
        </div>
      </div>
    </div>
  );
}
