"use client";
import React, { useEffect, useRef, useState } from "react";
import { api, PipelineStatus } from "../lib/api";

// ============ 采集状态脉搏（侧栏常驻） ============
// 解决「系统到底在不在干活」的核心焦虑：任何页面都能看到采集是否在跑、
// 上次采集何时、下次何时。轮询在这里常驻，切页不丢——立即采集后去别的页
// 逛一圈回来，进度仍在。空闲 20s 一拍、采集中 4s 一拍。

const MONO = "'JetBrains Mono', monospace";

// 后端 UTC naive 时间戳补 Z 解析；带时区的（APScheduler next_runs）原样解析
function toMs(iso?: string | null): number | undefined {
  if (!iso) return undefined;
  const d = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z");
  return isNaN(d.getTime()) ? undefined : d.getTime();
}

function hhmm(ms?: number): string {
  if (!ms) return "—";
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

function ago(ms?: number): string {
  if (!ms) return "—";
  const diff = Date.now() - ms;
  if (diff < 6e4) return "刚刚";
  if (diff < 36e5) return `${Math.floor(diff / 6e4)} 分钟前`;
  if (diff < 864e5) return `${Math.floor(diff / 36e5)} 小时前`;
  return `${Math.floor(diff / 864e5)} 天前`;
}

export default function StatusPulse({ onOpen }: { onOpen: () => void }) {
  const [st, setSt] = useState<PipelineStatus | null>(null);
  const [down, setDown] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      let crawling = false;
      try {
        const s = await api.pipelineStatus();
        if (!alive) return;
        setSt(s);
        setDown(false);
        crawling = s.manual_crawl?.status === "running";
      } catch {
        if (!alive) return;
        setDown(true);
      }
      timer.current = setTimeout(tick, crawling ? 4000 : 20000);
    };
    tick();
    return () => {
      alive = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const crawling = st?.manual_crawl?.status === "running";
  const srcErr = st?.sources?.error ?? 0;
  const lastMs = toMs(st?.articles?.last_crawled_at);
  const nextMs = toMs(st?.monitor?.next_runs?.crawl);
  const startedMs = toMs(st?.manual_crawl?.started_at);
  const runSecs = crawling && startedMs ? Math.max(0, Math.floor((Date.now() - startedMs) / 1000)) : 0;

  const dotColor = down ? "#FB7185" : crawling ? "#FCD34D" : srcErr > 0 ? "#FB923C" : "#4ADE80";
  const title = down ? "后端未连接" : crawling ? `采集中 · 已 ${runSecs} 秒` : "采集调度运行中";

  return (
    <div
      onClick={onOpen}
      title="点击查看流水线全景"
      style={{
        marginBottom: 10, padding: "10px 12px", borderRadius: 12, cursor: "pointer",
        background: crawling ? "rgba(252,211,77,0.06)" : "rgba(148,163,184,0.05)",
        border: `1px solid ${crawling ? "rgba(252,211,77,0.25)" : "rgba(148,163,184,0.10)"}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: dotColor,
          boxShadow: `0 0 8px ${dotColor}`,
          animation: crawling ? "pulse-dot 1.2s ease-in-out infinite" : undefined,
        }} />
        <span style={{ fontSize: 11.5, fontWeight: 700, color: down ? "#FDA4AF" : "#C4CDDD" }}>{title}</span>
      </div>
      {!down && st && (
        <div style={{ marginTop: 6, fontSize: 10.5, lineHeight: 1.8, color: "#5E6A82", fontFamily: MONO }}>
          <div>上次入库 {ago(lastMs)} · 24h 新增 {st.articles.added_24h}</div>
          <div>
            {st.monitor.enabled
              ? `下次自动采集 ${hhmm(nextMs)}`
              : "自动采集已关闭"}
            {srcErr > 0 && <span style={{ color: "#FB923C" }}> · {srcErr} 源异常</span>}
          </div>
        </div>
      )}
      {down && (
        <div style={{ marginTop: 6, fontSize: 10.5, lineHeight: 1.7, color: "#5E6A82" }}>
          请确认 FastAPI 后端已启动（8010）
        </div>
      )}
      <style>{`@keyframes pulse-dot { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }`}</style>
    </div>
  );
}
