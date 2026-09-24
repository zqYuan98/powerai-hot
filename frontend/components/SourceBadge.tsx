"use client";
import React from "react";
import { DataSource } from "../lib/useData";

// 标注当前数据来源：实时（后端）/ 演示（本地 mock）/ 加载中。
export default function SourceBadge({ source }: { source: DataSource }) {
  const map: Record<DataSource, { label: string; color: string; bg: string; bd: string }> = {
    backend: { label: "实时数据", color: "#6EE7B7", bg: "rgba(52,211,153,0.12)", bd: "rgba(52,211,153,0.3)" },
    mock: { label: "后端未连接", color: "#FB7185", bg: "rgba(251,113,133,0.12)", bd: "rgba(251,113,133,0.3)" },
    loading: { label: "加载中…", color: "#94A0B5", bg: "rgba(148,163,184,0.1)", bd: "rgba(148,163,184,0.22)" },
  };
  const s = map[source];
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 600,
        color: s.color, background: s.bg, border: `1px solid ${s.bd}`, padding: "4px 9px", borderRadius: 20,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, boxShadow: `0 0 8px ${s.color}` }} />
      {s.label}
    </span>
  );
}
