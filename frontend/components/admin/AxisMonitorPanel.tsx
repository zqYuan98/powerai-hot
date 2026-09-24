"use client";
import React, { useEffect, useState } from "react";
import { api, type AxisMonitorOut } from "../../lib/api";

/**
 * 双轴监控面板。
 *
 * 存在的理由：本产品的核心风险是「行业侧供给悄悄归零，退化成纯 AI 资讯站」——
 * 2026-07 就发生过（电力采集器全 0 产出、招标子站挂掉却显示绿灯，无人发现）。
 * power_supply_ratio 就是这个风险的单一观测指标。
 */

const AXIS_COLOR: Record<string, string> = {
  "交叉": "#F59E0B",
  "AI": "#A78BFA",
  "行业": "#34E0D8",
  "弱": "#6B7689",
};

const CARD: React.CSSProperties = {
  background: "rgba(148,163,184,0.05)",
  border: "1px solid rgba(148,163,184,0.14)",
  borderRadius: 12,
  padding: 16,
};

export default function AxisMonitorPanel() {
  const [data, setData] = useState<AxisMonitorOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);

  useEffect(() => {
    let alive = true;
    setError(null);
    api.axisMonitor(days)
      .then((value) => alive && setData(value))
      .catch(() => alive && setError("双轴监控加载失败"));
    return () => { alive = false; };
  }, [days]);

  if (error) return <div style={{ ...CARD, color: "#FCA5A5" }}>{error}</div>;
  if (!data) return <div style={{ ...CARD, color: "#6B7689" }}>正在加载双轴监控…</div>;

  const total = data.by_axis.reduce((sum, item) => sum + item.count, 0) || 1;
  const ratio = data.power_supply_ratio;
  // 行业侧供给低于 20% 视为告警：说明又退回纯 AI 资讯站了
  const ratioHealthy = ratio >= 20;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: "#F2F5FA", margin: 0 }}>双轴监控</h3>
        <div style={{ display: "flex", gap: 2, padding: 3, background: "rgba(148,163,184,0.08)", borderRadius: 10 }}>
          {[7, 14, 30].map((value) => (
            <button key={value} type="button" onClick={() => setDays(value)} aria-pressed={days === value}
              style={{ fontSize: 12, fontWeight: days === value ? 700 : 500, cursor: "pointer", padding: "4px 10px", borderRadius: 8, border: 0, color: days === value ? "#0A0E17" : "#94A0B5", background: days === value ? "linear-gradient(145deg,#9FD0FF,#3B9EFF)" : "transparent" }}>
              {value} 天
            </button>
          ))}
        </div>
        {/* 这个切换只改趋势线长度：占比与分布刻意用全量统计，短窗口样本不足会让判断随机跳动 */}
        <span style={{ fontSize: 11.5, color: "#6B7689" }}>仅影响下方趋势线</span>
      </div>

      <div style={{ ...CARD, borderColor: ratioHealthy ? "rgba(52,211,153,0.28)" : "rgba(251,113,133,0.34)" }}>
        <div style={{ fontSize: 12, color: "#94A0B5", marginBottom: 6 }}>行业侧供给占比（交叉 + 行业，全量）</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 30, fontWeight: 800, color: ratioHealthy ? "#6EE7B7" : "#FCA5A5" }}>{ratio}%</span>
          <span style={{ fontSize: 12, color: ratioHealthy ? "#6EE7B7" : "#FCA5A5" }}>
            {ratioHealthy ? "供给正常" : "偏低 —— 行业侧内容不足，正在退化为纯 AI 资讯站"}
          </span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
        {data.by_axis.map((item) => (
          <div key={item.axis} style={{ ...CARD, borderLeft: `3px solid ${AXIS_COLOR[item.axis] ?? "#6B7689"}` }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: AXIS_COLOR[item.axis] ?? "#94A0B5" }}>{item.axis}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 800, color: "#EAF2FF", margin: "4px 0" }}>
              {item.count}
              <span style={{ fontSize: 12, fontWeight: 500, color: "#6B7689" }}> / {Math.round((100 * item.count) / total)}%</span>
            </div>
            <div style={{ fontSize: 11.5, color: "#828EA3" }}>精选 {item.curated} · 交叉分 {item.avg_cross} · 质量 {item.avg_quality}</div>
          </div>
        ))}
      </div>

      <div style={{ ...CARD, overflowX: "auto" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#F2F5FA", marginBottom: 10 }}>各信源产出的轴分布</div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, minWidth: 520 }}>
          <thead>
            <tr style={{ color: "#94A0B5", textAlign: "left" }}>
              <th style={{ padding: "6px 8px", fontWeight: 600 }}>信源</th>
              <th style={{ padding: "6px 8px", fontWeight: 600 }}>分级</th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }}>总数</th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right", color: AXIS_COLOR["交叉"] }}>交叉</th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right", color: AXIS_COLOR["AI"] }}>AI</th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right", color: AXIS_COLOR["行业"] }}>行业</th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }}>均交叉分</th>
            </tr>
          </thead>
          <tbody>
            {data.by_source.map((row) => (
              <tr key={row.source} style={{ borderTop: "1px solid rgba(148,163,184,0.10)", color: "#C4CDDD" }}>
                <td style={{ padding: "6px 8px" }}>{row.source}</td>
                <td style={{ padding: "6px 8px", color: "#6B7689" }}>{row.tier}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace" }}>{row.count}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace", color: row.cross > 0 ? AXIS_COLOR["交叉"] : "#3A4152" }}>{row.cross}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace", color: "#828EA3" }}>{row.ai}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace", color: "#828EA3" }}>{row.power}</td>
                <td style={{ padding: "6px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace" }}>{row.avg_cross}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ ...CARD, overflowX: "auto" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#F2F5FA", marginBottom: 10 }}>逐日轴分布（断供预警）</div>
        <div style={{ display: "flex", gap: 6, alignItems: "flex-end", minHeight: 90, minWidth: 320 }}>
          {data.trend.map((day) => {
            const sum = day.cross + day.ai + day.power + day.weak || 1;
            return (
              <div key={day.day} style={{ flex: 1, minWidth: 26, display: "flex", flexDirection: "column", alignItems: "center", gap: 5 }}>
                <div title={`交叉 ${day.cross} · AI ${day.ai} · 行业 ${day.power} · 弱 ${day.weak}`}
                  style={{ width: "100%", height: 70, display: "flex", flexDirection: "column-reverse", borderRadius: 5, overflow: "hidden", background: "rgba(148,163,184,0.06)" }}>
                  <div style={{ height: `${(100 * day.cross) / sum}%`, background: AXIS_COLOR["交叉"] }} />
                  <div style={{ height: `${(100 * day.power) / sum}%`, background: AXIS_COLOR["行业"] }} />
                  <div style={{ height: `${(100 * day.ai) / sum}%`, background: AXIS_COLOR["AI"] }} />
                </div>
                <span style={{ fontSize: 10, color: "#6B7689", whiteSpace: "nowrap" }}>{day.day.slice(5)}</span>
              </div>
            );
          })}
          {data.trend.length === 0 && <span style={{ color: "#6B7689", fontSize: 12.5 }}>窗口内暂无数据</span>}
        </div>
      </div>
    </div>
  );
}
