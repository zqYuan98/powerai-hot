"use client";
import React, { useEffect, useRef, useState } from "react";
import { api, AdminConfig, CrawlResult, SystemStatus } from "../../lib/api";
import { Spark, Check, Plus } from "../icons";

const PROVIDER_LABEL: Record<string, string> = { deepseek: "DeepSeek", custom: "自定义模型", ollama: "Ollama（本地）" };

// 后端不可用时的兜底配置：只保证页面能渲染，调用量/成本一律为零——不显示编造数字
const OFFLINE_CONFIG: AdminConfig = {
  provider: "deepseek",
  valid_providers: ["deepseek", "custom", "ollama"],
  task_providers: {},
  usage: {},
  estimated_cost_cny: {},
  price_per_1k_cny: {},
};

export default function AdminModule({ onToast }: { onToast: (m: string) => void }) {
  const [cfg, setCfg] = useState<AdminConfig | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);
  // 采集轮询跨越数分钟，页面切走后停止轮询/停止 setState。
  // setup 里必须重置为 true：React 18 StrictMode（next dev 默认）会 setup→cleanup→setup，
  // 只在 cleanup 置 false 的话开发模式下 alive 永远是 false，轮询第一拍就退出——
  // 表现恰好是「点了立即采集没反应」。
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  const load = () => {
    api.getAdminConfig()
      .then((c) => { setCfg(c); setLive(true); })
      .catch(() => { setCfg(OFFLINE_CONFIG); setLive(false); });
    api.systemStatus().then(setSystemStatus).catch(() => setSystemStatus(null));
  };
  useEffect(load, []);

  const switchProvider = async (p: string) => {
    if (!cfg || p === cfg.provider) return;
    setBusy(true);
    try {
      const next = await api.setProvider(p);
      setCfg(next); setLive(true);
      onToast(`已切换分析模型：${PROVIDER_LABEL[p] ?? p}`);
    } catch {
      onToast("切换失败：后端未连接，配置未生效");
    } finally {
      setBusy(false);
    }
  };

  const [crawling, setCrawling] = useState(false);
  const [crawlMsg, setCrawlMsg] = useState<string | null>(null);

  const fmtStats = (s: CrawlResult) =>
    `采集 ${s.fetched} 条 · 新增 ${s.inserted} · 精选 ${s.curated} · 预筛过滤 ${s.prefiltered_out} · 去重跳过 ${s.skipped_duplicate}` +
    (s.rescored ? ` · 补打分 ${s.rescored}` : "") + ` · 模型 ${s.provider}`;

  // 轮询后台采集直到结束。baseSecs：恢复已进行中的采集时，从后端 started_at 推算的已耗时
  const pollCrawl = async (baseSecs: number) => {
    let secs = baseSecs;
    for (;;) {
      await new Promise((ok) => setTimeout(ok, 3000));
      if (!alive.current) return; // 页面已切走，停止轮询（侧栏脉搏仍在全局显示进度）
      secs += 3;
      let st;
      try {
        st = await api.crawlStatus();
      } catch {
        setCrawlMsg("状态查询失败：后端连接中断，采集可能仍在后台进行");
        break;
      }
      if (st.status === "running") {
        setCrawlMsg(`采集中… 已 ${secs} 秒（全信源抓取 + 逐条模型打分，通常需几分钟）`);
        if (secs >= 900) { setCrawlMsg("采集超过 15 分钟仍未结束，请查看后端日志"); break; }
        continue;
      }
      if (st.status === "done" && st.stats) {
        setCrawlMsg(fmtStats(st.stats));
        onToast(`采集完成：新增 ${st.stats.inserted} 条，精选 ${st.stats.curated} 条`);
        load();
      } else if (st.status === "error") {
        setCrawlMsg(`采集失败：${st.error ?? "未知错误"}`);
        onToast("采集失败，详情见管理后台");
      } else {
        setCrawlMsg("采集已结束（结果被新一轮覆盖或服务已重启）");
      }
      break;
    }
    if (alive.current) setCrawling(false);
  };

  // 挂载时向后端要采集状态：立即采集是后台任务，切页再回来必须能续上进度/看到上轮结果，
  // 否则用户会以为「点了没反应」。
  useEffect(() => {
    api.crawlStatus().then((st) => {
      if (!alive.current) return;
      if (st.status === "running") {
        setCrawling(true);
        const base = st.started_at ? Math.max(0, Math.floor((Date.now() - new Date(st.started_at + "Z").getTime()) / 1000)) : 0;
        setCrawlMsg(`采集进行中… 已 ${base} 秒（切页前启动的任务仍在跑）`);
        pollCrawl(base);
      } else if (st.status === "done" && st.stats) {
        setCrawlMsg(`上一轮：${fmtStats(st.stats)}`);
      } else if (st.status === "error") {
        setCrawlMsg(`上一轮采集失败：${st.error ?? "未知错误"}`);
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- 信源管理 ----
  const [sources, setSources] = useState<any[]>([]);
  const [form, setForm] = useState({ name: "", url: "", type: "RSS" });

  const loadSources = () => { api.listSources().then(setSources).catch(() => setSources([])); };
  useEffect(loadSources, []);

  const addSource = async () => {
    if (!form.name.trim() || !form.url.trim()) { onToast("请填写名称和 URL"); return; }
    try {
      await api.addSource({ name: form.name.trim(), url: form.url.trim(), type: form.type }, true);
      setForm({ name: "", url: "", type: "RSS" });
      onToast(`已添加并启用监控：${form.name.trim()}`);
      loadSources();
    } catch { onToast("添加失败：后端未连接"); }
  };
  const toggleSource = async (s: any) => {
    try {
      await api.setSourceStatus(s.id, s.status === "已采纳" ? "待审核" : "已采纳");
      loadSources();
    } catch { onToast("操作失败：后端未连接"); }
  };
  const removeSource = async (s: any) => {
    try { await api.deleteSource(s.id); loadSources(); } catch { onToast("删除失败"); }
  };

  // 采集是后台异步任务（全信源抓取+逐条打分需数分钟），启动后轮询状态直到结束
  const runCrawl = async () => {
    setCrawling(true);
    setCrawlMsg("正在启动采集…");
    try {
      const r = await api.crawlNow(15);
      if (r.status === "running") setCrawlMsg("已有一轮采集在进行，接续等待其完成…");
      await pollCrawl(0);
    } catch {
      setCrawlMsg("采集启动失败：后端未连接");
      onToast("采集启动失败：后端未连接");
      if (alive.current) setCrawling(false);
    }
  };

  const runTest = async () => {
    setBusy(true);
    try {
      const r = await api.testModel();
      onToast(`测试调用成功 · ${PROVIDER_LABEL[r.provider] ?? r.provider}`);
      load();
    } catch {
      onToast("测试失败：后端未连接或模型调用出错");
    } finally {
      setBusy(false);
    }
  };

  if (!cfg) return <div style={{ flex: 1, padding: 40, color: "#6B7689" }}>加载中…</div>;

  const totalCalls = Object.values(cfg.usage).reduce((s, u) => s + u.calls, 0);
  const totalCost = Object.values(cfg.estimated_cost_cny).reduce((s, v) => s + v, 0);

  return (
    <div style={{ flex: 1, minWidth: 0, overflow: "auto", padding: "30px 40px", position: "relative", zIndex: 1 }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
          <h2 style={{ margin: 0, fontSize: 24, fontWeight: 900, letterSpacing: "-0.02em", color: "#F4F7FB" }}>管理后台</h2>
          <span style={{ fontSize: 11, fontWeight: 600, color: live ? "#6EE7B7" : "#FCD34D", background: live ? "rgba(52,211,153,0.12)" : "rgba(251,191,36,0.12)", border: `1px solid ${live ? "rgba(52,211,153,0.3)" : "rgba(251,191,36,0.28)"}`, padding: "4px 9px", borderRadius: 20 }}>
            {live ? "已连接后端" : "后端未连接"}
          </span>
        </div>
        <p style={{ margin: "0 0 24px", fontSize: 13, color: "#828EA3" }}>AI 模型切换与调用量监控 · 不同任务可独立配置模型</p>

        {/* 模型切换 */}
        <div style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD", marginBottom: 12 }}>分析模型（默认 DeepSeek）</div>
        <div style={{ display: "flex", gap: 12, marginBottom: 28, flexWrap: "wrap" }}>
          {cfg.valid_providers.map((p) => {
            const active = p === cfg.provider;
            return (
              <button key={p} disabled={busy} onClick={() => switchProvider(p)}
                style={{
                  display: "flex", alignItems: "center", gap: 9, minWidth: 180, padding: "16px 18px", borderRadius: 14, cursor: busy ? "default" : "pointer", textAlign: "left",
                  background: active ? "linear-gradient(145deg, rgba(52,224,216,0.16), rgba(52,224,216,0.04))" : "rgba(148,163,184,0.05)",
                  border: `1px solid ${active ? "rgba(52,224,216,0.4)" : "rgba(148,163,184,0.14)"}`,
                }}>
                <div style={{ width: 34, height: 34, borderRadius: 10, background: active ? "linear-gradient(145deg,#34E0D8,#1FB6C9)" : "rgba(148,163,184,0.12)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Spark size={16} fill={active ? "#0A0E17" : "#94A0B5"} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: active ? "#EAF7F6" : "#C4CDDD" }}>{PROVIDER_LABEL[p] ?? p}</div>
                  <div style={{ fontSize: 11, color: "#6B7689" }}>{p === "custom" ? "OpenAI 兼容端点 · 按供应商计费" : cfg.price_per_1k_cny[p] ? `¥${cfg.price_per_1k_cny[p]}/千tokens` : "本地免费"}</div>
                </div>
                {active && <Check size={16} color="#34E0D8" />}
              </button>
            );
          })}
        </div>

        {/* 概览 */}
        <div style={{ display: "flex", gap: 12, marginBottom: 22 }}>
          {[
            { label: "当前模型", value: PROVIDER_LABEL[cfg.provider] ?? cfg.provider, color: "#8EE6E0" },
            { label: "累计调用", value: `${totalCalls} 次`, color: "#9FD0FF" },
            { label: "预估费用", value: `¥${totalCost.toFixed(3)}`, color: "#B79CFF" },
          ].map((s) => (
            <div key={s.label} style={{ flex: 1, padding: "16px 18px", background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 14 }}>
              <div style={{ fontSize: 11, color: "#6B7689", marginBottom: 6 }}>{s.label}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: s.color, fontFamily: "'Space Grotesk', sans-serif" }}>{s.value}</div>
            </div>
          ))}
        </div>

        {systemStatus && (
          <div style={{ border: "1px solid rgba(148,163,184,0.12)", borderRadius: 14, overflow: "hidden", marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "12px 18px", background: "rgba(148,163,184,0.04)", borderBottom: "1px solid rgba(148,163,184,0.1)" }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#DCE3EF" }}>生产运行状态</div>
              <div style={{ fontSize: 11, color: "#6B7689", fontFamily: "'JetBrains Mono', monospace" }}>{systemStatus.server_time.replace("T", " ").slice(0, 16)} UTC</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 0 }}>
              {[
                { label: "最新入库", value: systemStatus.freshness.latest_ingested_at ? systemStatus.freshness.latest_ingested_at.replace("T", " ").slice(0, 16) : "无", color: "#9FD0FF" },
                { label: "24h 新增", value: `${systemStatus.freshness.added_24h}`, color: "#8EE6E0" },
                { label: "降级比例", value: `${Math.round(systemStatus.degradation.ratio * 100)}%`, color: systemStatus.degradation.ratio > 0.3 ? "#FCD34D" : "#6EE7B7" },
                { label: "失败信源", value: `${systemStatus.failed_sources.length}`, color: systemStatus.failed_sources.length ? "#FB7185" : "#6EE7B7" },
              ].map((item) => (
                <div key={item.label} style={{ padding: "13px 18px", borderRight: "1px solid rgba(148,163,184,0.08)" }}>
                  <div style={{ fontSize: 11, color: "#6B7689", marginBottom: 5 }}>{item.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: item.color, fontFamily: "'JetBrains Mono', monospace" }}>{item.value}</div>
                </div>
              ))}
            </div>
            <div style={{ padding: "12px 18px", borderTop: "1px solid rgba(148,163,184,0.08)", fontSize: 12, color: "#94A0B5", lineHeight: 1.7 }}>
              最近任务：{systemStatus.latest_jobs.slice(0, 3).map((job) => `${job.job_name} ${job.status} +${job.inserted}`).join(" · ") || "暂无任务"}
            </div>
          </div>
        )}

        {/* 调用量明细 */}
        <div style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD", marginBottom: 12 }}>各模型调用量</div>
        <div style={{ border: "1px solid rgba(148,163,184,0.12)", borderRadius: 14, overflow: "hidden", marginBottom: 24 }}>
          <div style={{ display: "flex", padding: "12px 18px", fontSize: 11, color: "#6B7689", background: "rgba(148,163,184,0.04)", borderBottom: "1px solid rgba(148,163,184,0.1)" }}>
            <span style={{ flex: 2 }}>模型</span><span style={{ flex: 1, textAlign: "right" }}>调用次数</span><span style={{ flex: 1, textAlign: "right" }}>tokens</span><span style={{ flex: 1, textAlign: "right" }}>预估费用</span>
          </div>
          {cfg.valid_providers.map((p) => {
            const u = cfg.usage[p] ?? { calls: 0, tokens: 0 };
            return (
              <div key={p} style={{ display: "flex", padding: "13px 18px", fontSize: 13, color: "#C4CDDD", borderTop: "1px solid rgba(148,163,184,0.06)" }}>
                <span style={{ flex: 2, fontWeight: 600, color: "#DCE3EF" }}>{PROVIDER_LABEL[p] ?? p}</span>
                <span style={{ flex: 1, textAlign: "right", fontFamily: "'JetBrains Mono', monospace" }}>{u.calls}</span>
                <span style={{ flex: 1, textAlign: "right", fontFamily: "'JetBrains Mono', monospace" }}>{u.tokens.toLocaleString()}</span>
                <span style={{ flex: 1, textAlign: "right", fontFamily: "'JetBrains Mono', monospace", color: "#B79CFF" }}>¥{(cfg.estimated_cost_cny[p] ?? 0).toFixed(3)}</span>
              </div>
            );
          })}
        </div>

        {/* 信源管理 */}
        <div style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD", margin: "4px 0 12px" }}>信源管理（添加后自动持续监控）</div>
        <div style={{ border: "1px solid rgba(148,163,184,0.12)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="信源名称（如：北极星储能网）"
              style={{ flex: "1 1 180px", minWidth: 140, padding: "10px 12px", fontSize: 13, color: "#DCE3EF", background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.16)", borderRadius: 9, outline: "none" }} />
            <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="RSS / 网页 URL"
              style={{ flex: "2 1 260px", minWidth: 180, padding: "10px 12px", fontSize: 13, color: "#9FD0FF", fontFamily: "'JetBrains Mono', monospace", background: "rgba(59,158,255,0.05)", border: "1px solid rgba(59,158,255,0.22)", borderRadius: 9, outline: "none" }} />
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}
              style={{ padding: "10px 12px", fontSize: 13, color: "#DCE3EF", background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.16)", borderRadius: 9, outline: "none" }}>
              <option value="RSS">RSS</option>
              <option value="公众号">公众号</option>
              <option value="网站">网站</option>
            </select>
            <button onClick={addSource}
              style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 700, color: "#0A0E17", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", border: "none", padding: "10px 16px", borderRadius: 9, cursor: "pointer", whiteSpace: "nowrap" }}>
              <Plus color="#0A0E17" />添加信源
            </button>
          </div>
          <div style={{ fontSize: 11.5, color: "#6B7689", marginTop: 9, lineHeight: 1.7 }}>
            RSS / 公众号（RSS 桥地址）添加后即被自动监控；普通网站若无 RSS 需专用解析器（北极星已内置）。
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
          {sources.map((s) => {
            const active = s.status === "已采纳";
            // 后端 /sources 直接给出 builtin（内置采集器，始终在抓）与 crawlable；旧字段缺失时回退类型规则
            const monitored = s.builtin === true || (active && (s.crawlable ?? (s.type === "RSS" || s.type === "公众号")));
            return (
              <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 11 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", flexShrink: 0, background: monitored ? "#34E0D8" : "#586074", boxShadow: monitored ? "0 0 8px #34E0D8" : "none" }} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: "#DCE3EF" }}>{s.name} <span style={{ fontSize: 11, color: "#6B7689", fontWeight: 400 }}>· {s.type}</span></div>
                  <div style={{ fontSize: 11, color: "#6B7689", fontFamily: "'JetBrains Mono', monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.url}</div>
                </div>
                <span style={{ fontSize: 11, fontWeight: 600, color: monitored ? "#6EE7B7" : "#94A0B5", whiteSpace: "nowrap" }}>{monitored ? "监控中" : active ? "已采纳" : "未启用"}</span>
                <button onClick={() => toggleSource(s)} style={{ fontSize: 12, color: active ? "#FCD34D" : "#6EE7B7", background: "transparent", border: `1px solid ${active ? "rgba(251,191,36,0.3)" : "rgba(52,211,153,0.3)"}`, padding: "5px 10px", borderRadius: 8, cursor: "pointer" }}>{active ? "停用" : "启用"}</button>
                <button onClick={() => removeSource(s)} style={{ fontSize: 12, color: "#FB7185", background: "transparent", border: "1px solid rgba(251,113,133,0.3)", padding: "5px 10px", borderRadius: 8, cursor: "pointer" }}>删除</button>
              </div>
            );
          })}
          {sources.length === 0 && <div style={{ fontSize: 12.5, color: "#6B7689", padding: "8px 2px" }}>暂无信源。</div>}
        </div>

        {/* 信源采集 */}
        <div style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD", margin: "4px 0 12px" }}>信源采集</div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 18px", background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 14, marginBottom: 22 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#DCE3EF" }}>全部信源 · 立即采集</div>
            <div style={{ fontSize: 12, color: "#6B7689", marginTop: 3 }}>
              {crawlMsg ?? `内置采集器 + 已采纳的 RSS/公众号源一轮抓取 → ${PROVIDER_LABEL[cfg.provider] ?? cfg.provider} 逐条打分 → 高分自动进精选`}
            </div>
          </div>
          <button disabled={crawling} onClick={runCrawl}
            style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 700, color: "#0A0E17", background: "linear-gradient(145deg, #34E0D8, #1FB6C9)", border: "none", padding: "10px 18px", borderRadius: 10, cursor: crawling ? "default" : "pointer", boxShadow: "0 8px 22px -8px rgba(52,224,216,0.6)", opacity: crawling ? 0.7 : 1, whiteSpace: "nowrap" }}>
            <Spark size={14} fill="#0A0E17" />{crawling ? "采集中…" : "立即采集"}
          </button>
        </div>

        <button disabled={busy} onClick={runTest}
          style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 700, color: "#0A0E17", background: "linear-gradient(145deg, #34E0D8, #1FB6C9)", border: "none", padding: "11px 20px", borderRadius: 11, cursor: busy ? "default" : "pointer", boxShadow: "0 8px 22px -8px rgba(52,224,216,0.6)", opacity: busy ? 0.7 : 1 }}>
          <Spark size={15} fill="#0A0E17" />用当前模型测试摘要调用
        </button>

        <ScoringSection onToast={onToast} />
      </div>
    </div>
  );
}

function NumInput({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#94A0B5" }}>
      {label}
      <input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: 64, fontSize: 12.5, color: "#E6EBF4", background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.16)", borderRadius: 7, padding: "5px 8px" }} />
    </label>
  );
}

function ScoringSection({ onToast }: { onToast: (m: string) => void }) {
  const [cfg, setCfg] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.getScoring().then(setCfg).catch(() => setCfg(null)); }, []);
  if (!cfg) return null;

  const saveAndRecompute = async () => {
    setBusy(true);
    try {
      await api.putScoring({
        dim_weights: cfg.dim_weights, channel_thresholds: cfg.channel_thresholds,
        axis_threshold: cfg.axis_threshold, cross_threshold: cfg.cross_threshold,
        cross_quality_floor: cfg.cross_quality_floor,
        hot_score: cfg.hot_score, cluster_threshold: cfg.cluster_threshold,
      });
      const r = await api.recomputeScoring();
      onToast(`配置已保存，全库重算 ${r.recomputed} 篇`);
    } catch { onToast("保存失败"); }
    setBusy(false);
  };

  // 键名与 analyzer/scoring.py::DIM_KEYS 一一对应；缺项会退化成英文键名裸露在界面上
  const DIM_LABEL: Record<string, string> = {
    ai_relevance: "AI 相关", power_relevance: "行业相关",
    firsthand: "一手性", utility: "工程实用", impact: "影响力", depth: "内容深度",
  };

  return (
    <div style={{ marginTop: 20, padding: "18px 20px", background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.12)", borderRadius: 14 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#F2F5FA", marginBottom: 12 }}>评分配置（改完点保存即全库纯代码重算，不调模型）</div>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#485066", letterSpacing: "0.08em", margin: "8px 0 6px" }}>六维权重</div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        {Object.keys(cfg.dim_weights).map((k) => (
          <NumInput key={k} label={DIM_LABEL[k] ?? k} value={cfg.dim_weights[k]}
            onChange={(v) => setCfg({ ...cfg, dim_weights: { ...cfg.dim_weights, [k]: v } })} />
        ))}
      </div>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#485066", letterSpacing: "0.08em", margin: "12px 0 6px" }}>分频道精选阈值</div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        {Object.keys(cfg.channel_thresholds).map((k) => (
          <NumInput key={k} label={k} value={cfg.channel_thresholds[k]}
            onChange={(v) => setCfg({ ...cfg, channel_thresholds: { ...cfg.channel_thresholds, [k]: v } })} />
        ))}
      </div>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#485066", letterSpacing: "0.08em", margin: "12px 0 6px" }}>双轴阈值</div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <NumInput label="单轴高分线" value={cfg.axis_threshold} onChange={(v) => setCfg({ ...cfg, axis_threshold: v })} />
        <NumInput label="交叉精选线" value={cfg.cross_threshold} onChange={(v) => setCfg({ ...cfg, cross_threshold: v })} />
        <NumInput label="交叉质量下限" value={cfg.cross_quality_floor} onChange={(v) => setCfg({ ...cfg, cross_quality_floor: v })} />
      </div>
      <div style={{ fontSize: 11.5, color: "#6B7690", lineHeight: 1.6, marginTop: 6 }}>
        单轴高分线决定 axis 归类；两轴同时过线才算「交叉」。交叉内容走独立精选通道：
        cross_score ≥ 交叉精选线 且 quality ≥ 交叉质量下限即入选——质量下限刻意低于频道阈值，
        否则招标/政策类交叉情报会被体裁拖累而全部落选。
      </div>
      <div style={{ display: "flex", gap: 14, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
        <NumInput label="热点线" value={cfg.hot_score} onChange={(v) => setCfg({ ...cfg, hot_score: v })} />
        <NumInput label="聚类阈值" value={cfg.cluster_threshold} onChange={(v) => setCfg({ ...cfg, cluster_threshold: v })} />
        <button onClick={saveAndRecompute} disabled={busy}
          style={{ marginLeft: "auto", fontSize: 12.5, fontWeight: 700, color: "#0A0E17", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", border: "none", padding: "9px 18px", borderRadius: 9, cursor: "pointer", opacity: busy ? 0.5 : 1 }}>
          {busy ? "保存中…" : "保存并全库重算"}
        </button>
      </div>
    </div>
  );
}
