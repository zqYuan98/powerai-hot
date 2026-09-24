"use client";
import React, { useEffect, useMemo, useState } from "react";
import { api, SourceRow } from "../../lib/api";
import { DataSource } from "../../lib/useData";
import SourceBadge from "../SourceBadge";
import { Globe, Check, Triangle, X, Spark } from "../icons";

// 内置采集器：代码写死在 backend/services/ingest.py 的 build_collectors()，
// 始终参与采集、不可停用。是否内置/是否实际参与抓取由后端 /sources 的
// builtin / crawlable 字段给出（单一事实在 services/ingest.py），
// 这里的名字表只提供展示文案，并作为后端未连接时的静态兜底。
const BUILTIN_META: Record<string, { type: string; desc: string }> = {
  北极星电力网: { type: "解析器", desc: "电力行业资讯 · 资讯组每小时" },
  arXiv: { type: "论文", desc: "AI 论文 · 论文组每日" },
  "Hugging Face Papers": { type: "论文", desc: "HuggingFace 每日精选 · 论文组每日" },
};
const BUILTIN_NAMES = Object.keys(BUILTIN_META);
const isBuiltin = (s: SourceRow) => s.builtin ?? BUILTIN_NAMES.includes(s.name);
const builtinTypeOf = (s: SourceRow) => BUILTIN_META[s.name]?.type ?? s.type;
// 旧后端无 crawlable 字段时回退到与 build_collectors 相同的规则
const isCrawlable = (s: SourceRow) => s.crawlable ?? ((s.type === "RSS" || s.type === "公众号") && !!s.url);

const MONO = "'JetBrains Mono', monospace";
const CARD_BG = "rgba(148,163,184,0.05)";
const CARD_BD = "1px solid rgba(148,163,184,0.12)";

const STATUS_DOT: Record<string, string> = {
  已采纳: "#4ADE80",
  待审核: "#FCD34D",
  未通过: "#586074",
};

function fmtTime(iso?: string | null): string {
  if (!iso) return "从未抓取";
  // 后端写入 UTC naive 时间、序列化不带时区标记——补 Z 按 UTC 解析，再转浏览器本地时间
  const d = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z");
  if (isNaN(d.getTime())) return "—";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}

export default function SourcesModule({ onToast }: { onToast?: (msg: string) => void }) {
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [conn, setConn] = useState<DataSource>("loading");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const load = (initial = false) =>
    api
      .listSources()
      .then((rows) => {
        setSources(rows);
        setConn("backend");
      })
      .catch(() => {
        // 只有首次加载失败才判定「后端未连接」；操作后的刷新失败保留现有列表，
        // 避免一次瞬时网络错误让整页数据消失、误导用户去重启后端
        if (initial) setConn("mock");
        else onToast?.("列表刷新失败，稍后自动恢复");
      });

  useEffect(() => {
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- 派生统计（内置行与普通 DB 源分开） ----
  const builtinRows = useMemo(() => sources.filter(isBuiltin), [sources]);
  const dbSources = useMemo(() => sources.filter((s) => !isBuiltin(s)), [sources]);
  const adopted = useMemo(() => dbSources.filter((s) => s.status === "已采纳"), [dbSources]);
  const pending = useMemo(() => dbSources.filter((s) => s.status === "待审核"), [dbSources]);
  const rejected = useMemo(() => dbSources.filter((s) => s.status === "未通过"), [dbSources]);
  const crawling = useMemo(() => adopted.filter(isCrawlable), [adopted]);
  const adoptedNotCrawled = adopted.length - crawling.length;
  // 已采纳却缺 URL 的 RSS/公众号：配置问题（不同于"网站类无解析器"的已知限制），要醒目提示
  const missingUrl = useMemo(
    () => adopted.filter((s) => !s.url && (s.type === "RSS" || s.type === "公众号")),
    [adopted],
  );
  // 抓取异常只统计真正在抓的源（内置 + 已采纳可抓取），
  // 已采纳但不参与抓取的网站类源即使残留旧 error 也不算「在抓信源抓取失败」
  const errSources = useMemo(
    () => [...builtinRows, ...crawling].filter((s) => s.last_status === "error"),
    [builtinRows, crawling],
  );

  // 「在抓」= 内置 + 已采纳且实际参与调度的源。
  // 后端未连接、或 DB 未登记内置行（未跑 seed）时，退回静态内置名单展示
  const useBuiltinRows = conn === "backend" && builtinRows.length > 0;
  const builtinCount = useBuiltinRows ? builtinRows.length : BUILTIN_NAMES.length;
  const activeCount = builtinCount + crawling.length;
  const totalCount = builtinCount + dbSources.length;

  const typeDist = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of dbSources) m.set(s.type, (m.get(s.type) ?? 0) + 1);
    return Array.from(m.entries());
  }, [dbSources]);

  // 已采纳按 tier 分小节
  const adoptedByTier = useMemo(() => {
    const order = ["T1", "T1.5", "T2"];
    const map: Record<string, SourceRow[]> = {};
    for (const s of adopted) {
      const t = order.includes(s.tier ?? "") ? (s.tier as string) : "T2";
      if (!map[t]) map[t] = [];
      map[t].push(s);
    }
    return order.filter((t) => map[t] && map[t].length > 0).map((t) => ({ tier: t, items: map[t] }));
  }, [adopted]);

  // ---- 操作 ----
  const select = (id: number) => {
    setConfirmDelete(null);
    setSelectedId((cur) => (cur === id ? null : id));
  };

  const closePanel = () => {
    setSelectedId(null);
    setConfirmDelete(null);
  };

  const doStatus = async (s: SourceRow, status: string, verb: string) => {
    setBusy(true);
    setConfirmDelete(null); // 换了操作意图，撤销已点一次的删除确认
    try {
      await api.setSourceStatus(s.id, status);
      onToast?.(`${verb}「${s.name}」`);
      await load();
    } catch {
      onToast?.("操作失败：后端未连接或无管理权限");
    } finally {
      setBusy(false);
    }
  };

  // OPML 批量导入（RSS 阅读器通用导出格式）
  const [opmlOpen, setOpmlOpen] = useState(false);
  const [opmlText, setOpmlText] = useState("");
  const [opmlActive, setOpmlActive] = useState(false);

  const doImportOpml = async () => {
    if (!opmlText.trim()) return;
    setBusy(true);
    try {
      const r = await api.importOpml(opmlText, opmlActive);
      onToast?.(
        `导入 ${r.imported} 个信源` +
        (r.skipped ? `，跳过重复 ${r.skipped} 个` : "") +
        (r.errors.length ? `，${r.errors.length} 个 URL 未通过校验` : ""),
      );
      setOpmlText("");
      setOpmlOpen(false);
      await load();
    } catch {
      onToast?.("导入失败：OPML 格式有误、后端未连接或无管理权限");
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async (s: SourceRow) => {
    if (confirmDelete !== s.id) {
      setConfirmDelete(s.id);
      return;
    }
    setBusy(true);
    try {
      await api.deleteSource(s.id);
      onToast?.(`已删除「${s.name}」`);
      closePanel();
      await load();
    } catch {
      onToast?.("删除失败：后端未连接或无管理权限");
    } finally {
      setBusy(false);
    }
  };

  // 操作面板：渲染在所属分组网格下方
  const renderPanel = (list: SourceRow[]) => {
    const s = list.find((x) => x.id === selectedId);
    if (!s) return null;
    const builtin = isBuiltin(s);
    const isErr = s.last_status === "error";
    const btnBase: React.CSSProperties = {
      fontSize: 12.5,
      fontWeight: 700,
      padding: "7px 14px",
      borderRadius: 9,
      cursor: busy ? "default" : "pointer",
      background: "transparent",
      opacity: busy ? 0.55 : 1,
      whiteSpace: "nowrap",
    };
    return (
      <div
        style={{
          marginTop: 10,
          padding: "14px 16px",
          background: "rgba(148,163,184,0.06)",
          border: "1px solid rgba(52,224,216,0.28)",
          borderRadius: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#E6EBF4" }}>{s.name}</span>
          <span style={{ fontSize: 11, color: "#94A0B5", background: "rgba(148,163,184,0.10)", border: "1px solid rgba(148,163,184,0.14)", padding: "2px 8px", borderRadius: 20 }}>
            {builtin ? builtinTypeOf(s) : s.type}
          </span>
          <span style={{ fontSize: 11, color: "#A78BFA", background: "rgba(167,139,250,0.10)", border: "1px solid rgba(167,139,250,0.25)", padding: "2px 8px", borderRadius: 20, fontFamily: MONO }}>
            {s.tier || "T2"}
          </span>
          {builtin && (
            <span style={{ fontSize: 10, fontWeight: 700, color: "#34E0D8", background: "rgba(52,224,216,0.12)", padding: "2px 7px", borderRadius: 20 }}>内置</span>
          )}
          <span style={{ marginLeft: "auto", cursor: "pointer", color: "#5E6A82", display: "flex" }}>
            <X size={14} onClick={closePanel} />
          </span>
        </div>
        <div
          style={{
            marginTop: 8,
            fontSize: 11.5,
            color: s.url ? "#9FD0FF" : "#FCD34D",
            fontFamily: MONO,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {s.url || "（未填写 URL）"}
        </div>
        {!builtin && !s.url && (s.type === "RSS" || s.type === "公众号") && s.status === "已采纳" && (
          <div style={{ marginTop: 6, fontSize: 11.5, fontWeight: 700, color: "#FCD34D" }}>
            ⚠ 该源已采纳但没有 URL，不会被抓取——请删除后重新添加并填入 RSS 地址。
          </div>
        )}
        <div style={{ marginTop: 6, fontSize: 11.5, color: "#5E6A82", display: "flex", gap: 14, flexWrap: "wrap" }}>
          <span>提交人：{s.submitted_by || "—"}</span>
          <span>上次抓取：{fmtTime(s.last_crawled_at)}</span>
          <span style={{ color: isErr ? "#FB7185" : s.last_status === "ok" ? "#4ADE80" : "#5E6A82" }}>
            抓取状态：{isErr ? "异常" : s.last_status === "ok" ? "正常" : "无记录"}
          </span>
        </div>
        {isErr && s.last_error && (
          <div style={{ marginTop: 6, fontSize: 11.5, color: "#FB7185", fontFamily: MONO }}>
            {truncate(s.last_error, 120)}
          </div>
        )}
        {(s.article_count ?? 0) > 0 && (
          <div style={{ marginTop: 6, fontSize: 11.5, display: "flex", gap: 14, flexWrap: "wrap", fontFamily: MONO }}>
            <span style={{ color: "#5E6A82" }}>入库 {s.article_count}</span>
            <span
              title="被预筛判定为无关的比例。持续偏高说明这个源在消耗采集预算与模型调用。"
              style={{ color: (s.noise_pct ?? 0) >= 40 ? "#FB7185" : (s.noise_pct ?? 0) >= 20 ? "#FCD34D" : "#5E6A82" }}
            >
              噪音 {s.noise_pct ?? 0}%
            </span>
            <span
              title="产出的精选条数。长期为 0 且噪音高的源应当停用。"
              style={{ color: (s.curated_count ?? 0) > 0 ? "#4ADE80" : "#5E6A82" }}
            >
              精选 {s.curated_count ?? 0}
            </span>
            <span title="落在电力业务轴（交叉+行业）的条数" style={{ color: (s.power_count ?? 0) > 0 ? "#34E0D8" : "#5E6A82" }}>
              电力轴 {s.power_count ?? 0}
            </span>
          </div>
        )}
        {builtin ? (
          <div style={{ marginTop: 12, fontSize: 11.5, color: "#5E6A82" }}>
            内置采集器由代码定义（backend/services/ingest.py），始终参与采集，不可停用或删除。
          </div>
        ) : (
          <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            {s.status === "待审核" && (
              <button
                disabled={busy}
                onClick={() => doStatus(s, "已采纳", "已采纳")}
                style={{
                  ...btnBase,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  color: "#0A0E17",
                  background: "linear-gradient(145deg,#4ADE80,#22C55E)",
                  border: "none",
                }}
              >
                <Check size={13} color="#0A0E17" />
                {isCrawlable(s) ? "采纳并纳入采集" : "采纳（网站类暂不自动抓取）"}
              </button>
            )}
            {s.status === "已采纳" && (
              <button
                disabled={busy}
                onClick={() => doStatus(s, "未通过", "已停用")}
                style={{ ...btnBase, color: "#FCD34D", border: "1px solid rgba(252,211,77,0.32)" }}
              >
                停用
              </button>
            )}
            {s.status === "未通过" && (
              <button
                disabled={busy}
                onClick={() => doStatus(s, "已采纳", "已重新启用")}
                style={{ ...btnBase, color: "#4ADE80", border: "1px solid rgba(74,222,128,0.32)" }}
              >
                重新启用
              </button>
            )}
            <button
              disabled={busy}
              onClick={() => doDelete(s)}
              style={{
                ...btnBase,
                color: confirmDelete === s.id ? "#0A0E17" : "#FB7185",
                background: confirmDelete === s.id ? "#FB7185" : "transparent",
                border: "1px solid rgba(251,113,133,0.35)",
              }}
            >
              {confirmDelete === s.id ? "再点一次确认删除" : "删除"}
            </button>
            <span style={{ alignSelf: "center", fontSize: 11, color: "#5E6A82" }}>
              {isCrawlable(s)
                ? "已采纳的 RSS/公众号源自动参与调度采集"
                : "网站类源暂不参与自动抓取（尚无对应解析器）"}
            </span>
          </div>
        )}
      </div>
    );
  };

  const chip = (s: SourceRow) => {
    const isErr = s.status === "已采纳" && s.last_status === "error";
    const dot = isErr ? "#FB7185" : STATUS_DOT[s.status] ?? "#586074";
    const selected = selectedId === s.id;
    return (
      <button
        key={s.id}
        onClick={() => select(s.id)}
        title={s.url}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          padding: "7px 12px",
          borderRadius: 9,
          cursor: "pointer",
          fontSize: 12.5,
          fontWeight: 600,
          color: selected ? "#EAF7F6" : s.status === "未通过" ? "#8A94A8" : "#C4CDDD",
          background: selected ? "rgba(52,224,216,0.10)" : CARD_BG,
          border: `1px solid ${
            selected ? "rgba(52,224,216,0.45)" : isErr ? "rgba(251,113,133,0.35)" : "rgba(148,163,184,0.14)"
          }`,
          maxWidth: 260,
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            flexShrink: 0,
            background: dot,
            boxShadow: isErr ? "0 0 8px #FB7185" : s.status === "已采纳" ? `0 0 7px ${dot}` : "none",
          }}
        />
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.name}</span>
        <span style={{ color: "#5E6A82", fontWeight: 400, fontSize: 11, flexShrink: 0 }}>{s.type}</span>
      </button>
    );
  };

  // 内置采集器 chip：有对应 DB 行（seed 登记）则可点开看健康；没有则静态展示
  const builtinChip = (name: string) => {
    const row = builtinRows.find((r) => r.name === name);
    const isErr = row?.last_status === "error";
    const selected = row != null && selectedId === row.id;
    const dotColor = isErr ? "#FB7185" : "#34E0D8";
    return (
      <button
        key={name}
        title={BUILTIN_META[name]?.desc ?? "代码内置采集器"}
        onClick={row ? () => select(row.id) : undefined}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          padding: "7px 12px",
          borderRadius: 9,
          fontSize: 12.5,
          fontWeight: 600,
          color: "#C9F5F2",
          background: selected ? "rgba(52,224,216,0.14)" : "rgba(52,224,216,0.07)",
          border: `1px solid ${selected ? "rgba(52,224,216,0.5)" : isErr ? "rgba(251,113,133,0.4)" : "rgba(52,224,216,0.26)"}`,
          cursor: row ? "pointer" : "default",
        }}
      >
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: dotColor, boxShadow: `0 0 7px ${dotColor}`, flexShrink: 0 }} />
        {name}
        <span style={{ color: "#5E8B88", fontWeight: 400, fontSize: 11 }}>{BUILTIN_META[name]?.type ?? row?.type ?? ""}</span>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: "#34E0D8",
            background: "rgba(52,224,216,0.12)",
            padding: "1px 6px",
            borderRadius: 20,
            letterSpacing: "0.02em",
          }}
        >
          内置
        </span>
      </button>
    );
  };

  const groupTitle = (title: string, count: number, hint?: string) => (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8, margin: "22px 0 10px" }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: "#C4CDDD" }}>{title}</span>
      <span style={{ fontSize: 12, color: "#5E6A82", fontFamily: MONO }}>{count}</span>
      {hint && <span style={{ fontSize: 11, color: "#5E6A82" }}>{hint}</span>}
    </div>
  );

  return (
    <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ flex: 1, overflow: "auto", padding: "30px 40px", position: "relative", zIndex: 1 }}>
        <div style={{ maxWidth: 1080, margin: "0 auto" }}>
          {/* 页头大卡片 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              padding: "22px 26px",
              borderRadius: 16,
              background: "linear-gradient(145deg, rgba(59,158,255,0.10), rgba(52,224,216,0.05))",
              border: "1px solid rgba(148,163,184,0.14)",
              marginBottom: 16,
            }}
          >
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 13,
                background: "linear-gradient(145deg, rgba(59,158,255,0.22), rgba(52,224,216,0.14))",
                border: "1px solid rgba(59,158,255,0.3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Globe size={22} color="#9FD0FF" />
            </div>
            <div style={{ minWidth: 0 }}>
              <h2 style={{ margin: 0, fontSize: 24, fontWeight: 900, letterSpacing: "-0.02em", color: "#F4F7FB" }}>
                信源管理
              </h2>
              <p style={{ margin: "3px 0 0", fontSize: 13, color: "#828EA3" }}>
                {conn === "backend" ? (
                  <><span style={{ color: "#34E0D8", fontWeight: 700, fontFamily: MONO }}>{activeCount}</span> 个信源在抓
                  （含内置 {builtinCount} 个）· 资讯每小时 / 论文每日（默认调度）</>
                ) : (
                  <>内置 {BUILTIN_NAMES.length} 个采集器 · 资讯每小时 / 论文每日（默认调度）</>
                )}
              </p>
            </div>
            <div style={{ marginLeft: "auto", textAlign: "right", flexShrink: 0 }}>
              <SourceBadge source={conn} />
              {conn === "backend" && (
                <div style={{ fontSize: 11.5, color: "#94A0B5", marginTop: 8, fontFamily: MONO }}>
                  已停用 {rejected.length} · 待审核 {pending.length}
                </div>
              )}
            </div>
          </div>

          {/* 后端未连接提示 */}
          {conn === "mock" && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: 11,
                background: "rgba(251,113,133,0.08)",
                border: "1px solid rgba(251,113,133,0.28)",
                fontSize: 12.5,
                color: "#FDA4AF",
                marginBottom: 16,
              }}
            >
              后端未连接——数据库信源无法加载与管理，以下仅显示代码内置采集器。请确认 FastAPI 服务已启动。
            </div>
          )}

          {/* 统计卡片行 + 健康横幅：数字与健康结论都来自后端，未连接时不渲染，
              避免「抓取状态正常」和「后端未连接」同屏矛盾 */}
          {conn === "backend" && (<>
          <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
            {[
              {
                label: "在抓信源",
                value: String(activeCount),
                color: "#34E0D8",
                sub:
                  missingUrl.length > 0
                    ? `⚠ ${missingUrl.map((s) => s.name).join("、")} 缺 URL 未抓取`
                    : adoptedNotCrawled > 0
                    ? `另有 ${adoptedNotCrawled} 个网站类已采纳、暂不自动抓取`
                    : `总登记 ${totalCount} 个（含内置 ${builtinCount}）`,
              },
              {
                label: "抓取异常",
                value: String(errSources.length),
                color: errSources.length > 0 ? "#FB7185" : "#4ADE80",
                sub: errSources.length > 0 ? `${errSources.length} 个在抓信源上次抓取失败` : "运行平稳",
              },
              {
                label: "待审核",
                value: String(pending.length),
                color: "#FCD34D",
                sub: pending.length > 0 ? "等待审核后纳入采集池" : "暂无待审信源",
              },
              {
                label: "类型分布",
                value: [`内置×${builtinCount}`, ...typeDist.map(([t, n]) => `${t}×${n}`)].join(" "),
                color: "#A78BFA",
                sub: "内置解析器 + RSS / 公众号 / 网站",
                small: true,
              },
            ].map((c) => (
              <div
                key={c.label}
                style={{
                  flex: "1 1 200px",
                  minWidth: 180,
                  padding: "16px 18px",
                  background: CARD_BG,
                  border: CARD_BD,
                  borderRadius: 14,
                }}
              >
                <div style={{ fontSize: 11, color: "#6B7689", marginBottom: 8 }}>{c.label}</div>
                <div
                  style={{
                    fontSize: (c as any).small ? 15 : 27,
                    fontWeight: 800,
                    color: c.color,
                    fontFamily: MONO,
                    lineHeight: 1.2,
                    wordBreak: "break-all",
                  }}
                >
                  {c.value}
                </div>
                <div style={{ fontSize: 11, color: "#5E6A82", marginTop: 6 }}>{c.sub}</div>
              </div>
            ))}
          </div>

          {/* 健康横幅 */}
          {errSources.length === 0 ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "13px 16px",
                borderRadius: 12,
                background: "rgba(74,222,128,0.07)",
                border: "1px solid rgba(74,222,128,0.24)",
                marginBottom: 8,
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#4ADE80", boxShadow: "0 0 9px #4ADE80", flexShrink: 0 }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: "#86EFAC" }}>抓取状态正常</span>
              <span style={{ fontSize: 12, color: "#5E6A82" }}>当前没有抓取失败的在抓信源</span>
            </div>
          ) : (
            <div
              style={{
                padding: "13px 16px",
                borderRadius: 12,
                background: "rgba(251,113,133,0.07)",
                border: "1px solid rgba(251,113,133,0.3)",
                marginBottom: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <Triangle size={15} color="#FB7185" />
                <span style={{ fontSize: 13, fontWeight: 700, color: "#FDA4AF" }}>
                  {errSources.length} 个在抓信源抓取失败
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                {errSources.map((s) => (
                  <div key={s.id} style={{ fontSize: 12, color: "#C4CDDD", display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 700, color: "#FDA4AF", flexShrink: 0 }}>{s.name}</span>
                    <span style={{ color: "#94A0B5", fontFamily: MONO, fontSize: 11.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 520 }}>
                      {s.last_error || "未知错误"}
                    </span>
                    <span style={{ color: "#5E6A82", fontSize: 11, fontFamily: MONO, flexShrink: 0 }}>{fmtTime(s.last_crawled_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          </>)}

          {/* 信源地图 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "26px 0 2px" }}>
            <Spark size={14} fill="#A78BFA" />
            <span style={{ fontSize: 15, fontWeight: 800, color: "#F2F5FA", letterSpacing: "-0.01em" }}>信源地图</span>
            <span style={{ fontSize: 11.5, color: "#5E6A82" }}>点击信源查看详情与管理操作</span>
            {conn === "backend" && (
              <button
                onClick={() => setOpmlOpen((v) => !v)}
                style={{
                  marginLeft: "auto", fontSize: 12, fontWeight: 600, cursor: "pointer",
                  color: opmlOpen ? "#EAF7F6" : "#94A0B5",
                  background: opmlOpen ? "rgba(52,224,216,0.10)" : "rgba(148,163,184,0.06)",
                  border: `1px solid ${opmlOpen ? "rgba(52,224,216,0.45)" : "rgba(148,163,184,0.16)"}`,
                  padding: "6px 12px", borderRadius: 9,
                }}
              >
                导入 OPML
              </button>
            )}
          </div>

          {/* OPML 批量导入面板 */}
          {opmlOpen && conn === "backend" && (
            <div
              style={{
                marginTop: 10, padding: "14px 16px", borderRadius: 12,
                background: "rgba(148,163,184,0.06)", border: "1px solid rgba(52,224,216,0.28)",
              }}
            >
              <div style={{ fontSize: 12.5, color: "#94A0B5", marginBottom: 8 }}>
                粘贴 RSS 阅读器导出的 OPML 内容，批量登记其中的订阅源（按 URL / 名称自动去重）。
              </div>
              <textarea
                value={opmlText}
                onChange={(e) => setOpmlText(e.target.value)}
                placeholder={'<opml version="2.0">\n  <body>\n    <outline text="源名称" type="rss" xmlUrl="https://..."/>\n  </body>\n</opml>'}
                style={{
                  width: "100%", minHeight: 110, resize: "vertical", boxSizing: "border-box",
                  background: "rgba(10,14,23,0.6)", border: "1px solid rgba(148,163,184,0.18)",
                  borderRadius: 9, padding: "10px 12px", color: "#C4CDDD",
                  fontFamily: MONO, fontSize: 12, outline: "none",
                }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
                <button
                  disabled={busy || !opmlText.trim()}
                  onClick={doImportOpml}
                  style={{
                    fontSize: 12.5, fontWeight: 700, padding: "7px 16px", borderRadius: 9,
                    cursor: busy || !opmlText.trim() ? "default" : "pointer",
                    opacity: busy || !opmlText.trim() ? 0.55 : 1,
                    color: "#0A0E17", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", border: "none",
                  }}
                >
                  导入
                </button>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#94A0B5", cursor: "pointer" }}>
                  <input type="checkbox" checked={opmlActive} onChange={(e) => setOpmlActive(e.target.checked)} />
                  直接采纳并纳入采集（不勾选则进「待审核」）
                </label>
              </div>
            </div>
          )}

          {/* ① 内置采集器：已连接时按后端 builtin 标记渲染（新增内置源自动出现），
              未连接时用静态名单兜底展示 */}
          {groupTitle("内置采集器", builtinCount, "代码内置 · 始终参与采集 · 不可停用")}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {useBuiltinRows ? builtinRows.map((r) => builtinChip(r.name)) : BUILTIN_NAMES.map((n) => builtinChip(n))}
          </div>
          {conn === "backend" && renderPanel(builtinRows)}

          {/* 加载中 */}
          {conn === "loading" && (
            <div style={{ fontSize: 12.5, color: "#5E6A82", marginTop: 22 }}>正在加载数据库信源…</div>
          )}

          {/* ② 已采纳（按 tier 分小节） */}
          {conn === "backend" && (
            <>
              {groupTitle("已采纳", adopted.length, "RSS / 公众号自动参与采集；网站类暂不抓取")}
              {adopted.length === 0 && (
                <div style={{ fontSize: 12.5, color: "#5E6A82" }}>
                  暂无已采纳的数据库信源，可在「信源提报」页提交，或在管理后台直接添加并启用。
                </div>
              )}
              {adoptedByTier.map((g) => (
                <div key={g.tier} style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#485066", letterSpacing: "0.08em", margin: "6px 0 7px", fontFamily: MONO }}>
                    {g.tier}
                    <span style={{ marginLeft: 6, color: "#3C4356", fontWeight: 400 }}>
                      {g.tier === "T1" ? "核心信源" : g.tier === "T1.5" ? "重点信源" : "常规信源"}
                    </span>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{g.items.map(chip)}</div>
                  {renderPanel(g.items)}
                </div>
              ))}

              {/* ③ 待审核 */}
              {groupTitle("待审核", pending.length, "采纳后纳入采集池")}
              {pending.length === 0 ? (
                <div style={{ fontSize: 12.5, color: "#5E6A82" }}>暂无待审核信源。</div>
              ) : (
                <>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{pending.map(chip)}</div>
                  {renderPanel(pending)}
                </>
              )}

              {/* ④ 未通过 / 已停用 */}
              {groupTitle("未通过 / 已停用", rejected.length, "可重新启用或删除")}
              {rejected.length === 0 ? (
                <div style={{ fontSize: 12.5, color: "#5E6A82" }}>暂无停用信源。</div>
              ) : (
                <>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{rejected.map(chip)}</div>
                  {renderPanel(rejected)}
                </>
              )}
            </>
          )}

          <div style={{ height: 40 }} />
        </div>
      </div>
    </main>
  );
}
