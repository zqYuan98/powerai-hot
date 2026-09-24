"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api, mapArticle, type ArticleFreshness, type ArticleQuery, type ArticleTimelineOut } from "../../lib/api";
import type { Article, Channel } from "../../lib/types";
import type { DataSource } from "../../lib/useData";
import { useIsMobile } from "../../lib/useViewport";
import ArticleCard from "./ArticleCard";
import { getReadIds, markRead } from "../../lib/readStore";
import SourceBadge from "../SourceBadge";
import { Bell, Search, Sort, Spark } from "../icons";

const TABS: { name: Channel; spark?: boolean }[] = [
  { name: "行业动态" }, { name: "国网规划" }, { name: "招标公告" },
  { name: "AI洞察", spark: true }, { name: "政策法规" },
  { name: "前沿论文", spark: true }, { name: "大模型动态" }, { name: "落地案例" },
];

const PAGE_SIZE = 30;

export default function FeedModule({
  onGoSub, favIds, onToggleFav, subKeywords,
}: {
  onGoSub: () => void;
  favIds: Record<number, boolean>; onToggleFav: (a: Article) => void; subKeywords: string[];
}) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const [tab, setTab] = useState<Channel>("行业动态");
  const [threadId, setThreadId] = useState<number | undefined>();
  const [threadCounts, setThreadCounts] = useState<Array<{ id: number | null; name: string; count: number }>>([]);
  const [view] = useState<"精选" | "全部" | "噪音">("精选");
  const [win, setWin] = useState<"24h" | "7天" | "全部">("全部");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [curatedSort, setCuratedSort] = useState<"分数" | "最新">("分数");
  const [axis, setAxis] = useState<"全部轴" | "交叉" | "AI" | "行业">("全部轴");
  const [searchDraft, setSearchDraft] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const [articles, setArticles] = useState<Article[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [freshness, setFreshness] = useState<ArticleFreshness | null>(null);
  const [timeline, setTimeline] = useState<ArticleTimelineOut | null>(null);
  const [hasNew, setHasNew] = useState(false);
  const latestSeen = useRef<string | null>(null);
  const [readIds, setReadIds] = useState<Set<number>>(new Set());
  useEffect(() => { setReadIds(getReadIds()); }, []);
  const [hotTop, setHotTop] = useState<Article[]>([]);
  const [crossPicks, setCrossPicks] = useState<Article[]>([]);
  const [source, setSource] = useState<DataSource>("loading");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const autoPicked = useRef(false);

  const query = useMemo<ArticleQuery>(() => ({
    channel: tab,
    threadId,
    q: searchQuery || undefined,
    view: view === "精选" ? "curated" : view === "全部" ? "all" : "noise",
    window: win === "24h" ? "24h" : win === "7天" ? "7d" : "all",
    tag: activeTag || undefined,
    axis: axis === "全部轴" ? undefined : axis,
    sort: view === "精选" && curatedSort === "分数" ? "score" : "latest",
    limit: PAGE_SIZE,
  }), [activeTag, axis, curatedSort, searchQuery, tab, threadId, view, win]);

  const loadFirstPage = useCallback(async (activeQuery: ArticleQuery) => {
    const current = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const page = await api.listArticles(activeQuery);
      if (generation.current !== current) return;
      setArticles(page.items.map(mapArticle));
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
      setTotal(page.total);
      setSource("backend");
      void api.articleChannels(activeQuery).then((channelRows) => {
        if (generation.current === current) {
          setCounts(Object.fromEntries(channelRows.map((row) => [row.name, row.count])));
        }
      }).catch(() => undefined);
      void api.articleFreshness().then((fresh) => {
        if (generation.current === current) setFreshness(fresh);
      }).catch(() => undefined);
    } catch {
      if (generation.current !== current) return;
      setSource("mock");
      setError("情报加载失败，请检查服务连接后重试。");
    } finally {
      if (generation.current === current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadFirstPage(query);
  }, [loadFirstPage, query]);

  useEffect(() => {
    let active = true;
    api.threadSummary().then((rows) => { if (active) setThreadCounts(rows); }).catch(() => { if (active) setThreadCounts([]); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    api.articleHotspots(5)
      .then((rows) => { if (active) setHotTop(rows.map(mapArticle)); })
      .catch(() => { if (active) setHotTop([]); });
    api.articleCrossPicks(4)
      .then((rows) => { if (active) setCrossPicks(rows.map(mapArticle)); })
      .catch(() => { if (active) setCrossPicks([]); });
    return () => { active = false; };
  }, []);

  const loadTimeline = useCallback(() => {
    api.articleTimeline(48).then(setTimeline).catch(() => undefined);
  }, []);

  useEffect(() => { loadTimeline(); }, [loadTimeline]);

  useEffect(() => { latestSeen.current = freshness?.latest_crawled_at ?? latestSeen.current; }, [freshness]);

  // 轻量心跳：每 60s 只拉几十字节的 freshness；发现新入库时给提示、由用户点击加载，
  // 不自动重拉列表（尊重「后台静置不重复下载全量数据」的性能基线）。
  useEffect(() => {
    const id = setInterval(() => {
      api.articleFreshness().then((fresh) => {
        if (latestSeen.current && fresh.latest_crawled_at && fresh.latest_crawled_at !== latestSeen.current) {
          setHasNew(true);
        }
        setFreshness(fresh);
      }).catch(() => undefined);
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  // 距上次入库的小时数；超过 2 个采集周期视为「采集可能停了」
  const staleHours = useMemo(() => {
    const iso = timeline?.latest_crawled_at ?? freshness?.latest_crawled_at;
    if (!iso) return null;
    const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
    const ms = Date.now() - new Date(normalized).getTime();
    return Number.isNaN(ms) ? null : ms / 36e5;
  }, [timeline, freshness]);
  const isStale = staleHours !== null && staleHours >= 2;

  useEffect(() => {
    if (autoPicked.current || loading || Object.keys(counts).length === 0) return;
    autoPicked.current = true;
    if ((counts[tab] ?? 0) > 0) return;
    const best = Object.entries(counts).sort((left, right) => right[1] - left[1])[0];
    if (best && best[1] > 0) setTab(best[0] as Channel);
  }, [counts, loading, tab]);

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    const current = generation.current;
    setLoadingMore(true);
    setError(null);
    try {
      const page = await api.listArticles({ ...query, cursor: nextCursor });
      if (generation.current !== current) return;
      setArticles((existing) => {
        const byId = new Map(existing.map((article) => [article.id, article]));
        page.items.map(mapArticle).forEach((article) => byId.set(article.id, article));
        return [...byId.values()];
      });
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
      setTotal(page.total);
    } catch {
      if (generation.current === current) setError("加载更多失败，已保留当前列表。");
    } finally {
      if (generation.current === current) setLoadingMore(false);
    }
  };

  const submitSearch = () => setSearchQuery(searchDraft.trim());
  const agoLabel = (iso?: string | null): string => {
    if (!iso) return "—";
    const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
    const diff = Date.now() - new Date(normalized).getTime();
    if (diff < 6e4) return "刚刚";
    if (diff < 36e5) return `${Math.floor(diff / 6e4)} 分钟前`;
    if (diff < 864e5) return `${Math.floor(diff / 36e5)} 小时前`;
    return `${Math.floor(diff / 864e5)} 天前`;
  };
  const dayLabel = (ms?: number): string => {
    if (ms === undefined) return "更早";
    const date = new Date(ms);
    const today = new Date();
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
    if (ms >= start) return "今天";
    if (ms >= start - 864e5) return "昨天";
    return `${date.getMonth() + 1}月${date.getDate()}日`;
  };
  const showDayHeaders = view !== "精选" || curatedSort === "最新";

  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex" }}>
      <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: isMobile ? 10 : 16, padding: isMobile ? "12px 14px" : "18px 26px", borderBottom: "1px solid rgba(148,163,184,0.10)", flexShrink: 0 }}>
          <form onSubmit={(event) => { event.preventDefault(); submitSearch(); }} role="search" style={{ position: "relative", flex: "1 1 220px", maxWidth: isMobile ? undefined : 500, display: "flex" }}>
            <span style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", zIndex: 1 }}><Search /></span>
            <input
              type="search" aria-label="搜索情报" value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); submitSearch(); } }}
              placeholder="搜索情报、机构、关键词…"
              style={{ width: "100%", padding: "11px 86px 11px 40px", borderRadius: 11, background: "rgba(148,163,184,0.06)", border: searchQuery ? "1px solid rgba(52,224,216,0.42)" : "1px solid rgba(148,163,184,0.12)", outline: "none", fontSize: 13, color: "#DDE6F4", boxShadow: searchQuery ? "0 0 0 3px rgba(52,224,216,0.06)" : "none" }}
            />
            <button type="submit" style={{ position: "absolute", right: 5, top: 5, bottom: 5, padding: "0 13px", borderRadius: 8, border: "1px solid rgba(52,224,216,0.25)", background: "rgba(52,224,216,0.10)", color: "#8EE6E0", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>检索</button>
          </form>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            {source === "backend" && freshness && (
              <button type="button" onClick={() => { setHasNew(false); void loadFirstPage(query); loadTimeline(); }} title="立即刷新当前查询" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: isStale ? "#FCA5A5" : "#94A0B5", cursor: "pointer", padding: "5px 10px", borderRadius: 20, background: isStale ? "rgba(251,113,133,0.08)" : "rgba(148,163,184,0.07)", border: isStale ? "1px solid rgba(251,113,133,0.28)" : "1px solid rgba(148,163,184,0.14)", whiteSpace: isMobile ? "normal" : "nowrap", textAlign: "left" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: isStale ? "#FB7185" : "#4ADE80", boxShadow: isStale ? "0 0 6px #FB7185" : "0 0 6px #4ADE80", flexShrink: 0 }} />
                最新入库 {agoLabel(freshness.latest_crawled_at)} · 24h 新增 <b style={{ color: "#8EE6E0" }}>{freshness.added_24h}</b>（精选 {freshness.curated_24h}）
              </button>
            )}
            <SourceBadge source={source} />
            {!isMobile && subKeywords.slice(0, 3).map((keyword) => <span key={keyword} style={{ fontSize: 12, color: "#9FD0FF", background: "rgba(59,158,255,0.12)", border: "1px solid rgba(59,158,255,0.22)", padding: "5px 10px", borderRadius: 20 }}>{keyword}</span>)}
          </div>
          <button type="button" aria-label="打开推送订阅" onClick={onGoSub} style={{ position: "relative", width: 40, height: 40, borderRadius: 11, background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.12)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
            <Bell color="#B7C0D2" /><span style={{ position: "absolute", top: 8, right: 9, width: 7, height: 7, borderRadius: "50%", background: "#FB7185", boxShadow: "0 0 8px #FB7185" }} />
          </button>
        </div>

        {timeline && timeline.buckets.length > 0 && (() => {
          const maxCount = Math.max(1, ...timeline.buckets.map((b) => b.count));
          const total = timeline.buckets.reduce((sum, b) => sum + b.count, 0);
          const curatedTotal = timeline.buckets.reduce((sum, b) => sum + b.curated, 0);
          const hourLabel = (iso: string) => {
            const d = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);
            if (Number.isNaN(d.getTime())) return "—";
            const p = (n: number) => String(n).padStart(2, "0");
            return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:00`;
          };
          const staleLabel = staleHours === null ? "" : staleHours >= 24 ? `${Math.floor(staleHours / 24)} 天` : `${Math.floor(staleHours)} 小时`;
          return (
            <div aria-label="入库时间线" style={{ padding: isMobile ? "10px 14px 0" : "12px 26px 0", flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#8EA0C0" }}>入库时间线 · 近 48h</span>
                <span style={{ fontSize: 11.5, color: "#5E6A82", fontFamily: "'JetBrains Mono', monospace" }}>共 {total} 条 · 精选 {curatedTotal}</span>
                {isStale && (
                  <span style={{ fontSize: 11.5, fontWeight: 600, color: "#FCD34D", background: "rgba(251,191,36,0.10)", border: "1px solid rgba(251,191,36,0.24)", padding: "3px 10px", borderRadius: 14 }}>
                    ⚠ 已 {staleLabel} 无新入库 · 采集可能未运行（后端进程需常驻）
                  </span>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 34, overflowX: "auto" }}>
                {timeline.buckets.map((b) => (
                  <span
                    key={b.ts}
                    title={`${hourLabel(b.ts)} · 入库 ${b.count} 条${b.curated ? `（精选 ${b.curated}）` : ""}`}
                    style={{
                      flex: "1 0 3px",
                      minWidth: 3,
                      borderRadius: 2,
                      height: b.count > 0 ? 5 + Math.round(27 * (b.count / maxCount)) : 2,
                      background: b.count > 0
                        ? (b.curated > 0 ? "linear-gradient(180deg,#34E0D8,#1FB6C9)" : "rgba(59,158,255,0.55)")
                        : "rgba(148,163,184,0.16)",
                    }}
                  />
                ))}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#5E6A82", fontFamily: "'JetBrains Mono', monospace", marginTop: 3 }}>
                <span>{hourLabel(timeline.buckets[0].ts)}</span>
                <span>{hourLabel(timeline.buckets[timeline.buckets.length - 1].ts)}（现在）</span>
              </div>
            </div>
          );
        })()}

        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 4, padding: isMobile ? "6px 14px 0" : "14px 26px 0", flexShrink: 0 }}>
          {threadCounts.length > 0 && <div style={{ display: "flex", alignItems: "center", gap: 4, overflowX: "auto", maxWidth: "100%" }}>
            <button type="button" onClick={() => setThreadId(undefined)} aria-current={threadId === undefined ? "page" : undefined} style={{ padding: "7px 10px", cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap", background: "transparent", color: threadId === undefined ? "#8EE6E0" : "#828EA3", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 7 }}>全部主线</button>
            {threadCounts.filter((item) => item.id !== null).map((item) => <button key={item.id} type="button" onClick={() => setThreadId(item.id ?? undefined)} aria-current={threadId === item.id ? "page" : undefined} style={{ padding: "7px 10px", cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap", background: threadId === item.id ? "rgba(52,224,216,0.12)" : "transparent", color: threadId === item.id ? "#8EE6E0" : "#828EA3", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 7 }}>{item.name} {item.count}</button>)}
          </div>}
          <div style={{ display: "flex", alignItems: "center", gap: 4, overflowX: "auto", maxWidth: "100%" }}>
          {TABS.map((item) => {
            const active = tab === item.name;
            return <button key={item.name} type="button" onClick={() => setTab(item.name)} aria-current={active ? "page" : undefined} style={{ position: "relative", padding: isMobile ? "10px 11px 14px" : "10px 16px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, flexShrink: 0, whiteSpace: "nowrap", background: "transparent", border: 0 }}>
              {item.spark && <Spark size={14} />}<span style={{ fontSize: isMobile ? 14 : 15, fontWeight: active ? 700 : 500, color: active ? "#F2F5FA" : "#828EA3" }}>{item.name}</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: active ? "#3B9EFF" : "#586074" }}>{counts[item.name] ?? 0}</span>
              {active && <span style={{ position: "absolute", left: 12, right: 12, bottom: 0, height: 2.5, borderRadius: 3, background: "linear-gradient(90deg,#3B9EFF,#34E0D8)" }} />}
            </button>;
          })}
          </div>
          <div style={{ marginLeft: isMobile ? 0 : "auto", padding: "8px 0 14px", display: "flex", alignItems: "center", gap: isMobile ? 8 : 12, overflowX: "auto", maxWidth: "100%" }}>
            <div style={{ display: "flex", gap: 2, padding: 3, background: "rgba(148,163,184,0.08)", borderRadius: 10, flexShrink: 0 }}>
              {(["24h", "7天", "全部"] as const).map((value) => <button key={value} type="button" onClick={() => setWin(value)} style={{ fontSize: 12.5, fontWeight: win === value ? 700 : 500, cursor: "pointer", padding: "5px 11px", borderRadius: 8, whiteSpace: "nowrap", color: win === value ? "#0A0E17" : "#94A0B5", background: win === value ? "linear-gradient(145deg,#9FD0FF,#3B9EFF)" : "transparent", border: 0 }}>{value}</button>)}
            </div>
            <div role="group" aria-label="双轴筛选" style={{ display: "flex", gap: 2, padding: 3, background: "rgba(148,163,184,0.08)", borderRadius: 10, flexShrink: 0 }}>
              {(["全部轴", "交叉", "AI", "行业"] as const).map((value) => <button key={value} type="button" onClick={() => setAxis(value)} aria-pressed={axis === value} title={value === "交叉" ? "AI 技术轴与电力业务轴同时命中" : value === "AI" ? "仅 AI 技术轴" : value === "行业" ? "仅电力业务轴" : "不按轴筛选"} style={{ fontSize: 12.5, fontWeight: axis === value ? 700 : 500, cursor: "pointer", padding: "5px 11px", borderRadius: 8, whiteSpace: "nowrap", color: axis === value ? "#0A0E17" : "#94A0B5", background: axis === value ? (value === "交叉" ? "linear-gradient(145deg,#FBBF24,#F59E0B)" : "linear-gradient(145deg,#C4B5FD,#A78BFA)") : "transparent", border: 0 }}>{value}</button>)}
            </div>
            <div title="阅读端只展示通过推荐门槛且无噪音标记的情报" style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 10px", color: "#8EE6E0", background: "rgba(52,224,216,0.08)", border: "1px solid rgba(52,224,216,0.20)", borderRadius: 10, flexShrink: 0, fontSize: 12, fontWeight: 700, whiteSpace: "nowrap" }}>
              <Spark size={12} /> 仅显示精选
            </div>
            {view === "精选" ? <div style={{ display: "flex", gap: 2, padding: 3, background: "rgba(148,163,184,0.08)", borderRadius: 10, flexShrink: 0 }}>
              {(["分数", "最新"] as const).map((value) => <button key={value} type="button" onClick={() => setCuratedSort(value)} style={{ fontSize: 12.5, fontWeight: curatedSort === value ? 700 : 500, cursor: "pointer", padding: "5px 11px", borderRadius: 8, whiteSpace: "nowrap", color: curatedSort === value ? "#0A0E17" : "#94A0B5", background: curatedSort === value ? "linear-gradient(145deg,#FDBA74,#FB923C)" : "transparent", border: 0 }}>{value}</button>)}
            </div> : <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#6B7689", fontSize: 12, whiteSpace: "nowrap", flexShrink: 0 }}><Sort /><span>最新优先</span></div>}
          </div>
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: isMobile ? "14px 14px 84px" : "18px 26px 26px", display: "flex", flexDirection: "column", gap: 14 }}>
          {hasNew && (
            <button
              type="button"
              onClick={() => { setHasNew(false); void loadFirstPage(query); loadTimeline(); }}
              style={{ position: "sticky", top: 0, zIndex: 5, alignSelf: "center", fontSize: 12.5, fontWeight: 700, color: "#0A0E17", background: "linear-gradient(145deg,#34E0D8,#1FB6C9)", border: "none", padding: "8px 18px", borderRadius: 20, cursor: "pointer", boxShadow: "0 8px 20px -6px rgba(31,182,201,0.7)" }}
            >
              ⟳ 有新情报入库 · 点击加载
            </button>
          )}
          {(activeTag || searchQuery) && <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "#94A0B5" }}>
            <span>当前筛选</span>
            {searchQuery && <button type="button" onClick={() => { setSearchDraft(""); setSearchQuery(""); }} style={{ border: "1px solid rgba(59,158,255,0.32)", background: "rgba(59,158,255,0.10)", color: "#9FD0FF", borderRadius: 20, padding: "5px 12px", cursor: "pointer" }}>搜索：{searchQuery} ×</button>}
            {activeTag && <button type="button" onClick={() => setActiveTag(null)} style={{ border: "1px solid rgba(52,224,216,0.32)", background: "rgba(52,224,216,0.10)", color: "#8EE6E0", borderRadius: 20, padding: "5px 12px", cursor: "pointer" }}>标签：{activeTag} ×</button>}
            <span style={{ color: "#5E6A82" }}>共 {total} 条</span>
          </div>}

          {!activeTag && !searchQuery && axis === "全部轴" && crossPicks.length > 0 && <div style={{ marginBottom: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, margin: "2px 0 10px", flexWrap: "wrap" }}>
              <span style={{ fontSize: 14, fontWeight: 800, color: "#FBBF24" }}>⬥ 交叉精选</span>
              <span style={{ fontSize: 11.5, color: "#5E6A82" }}>AI 技术轴 × 电力业务轴同时命中</span>
              <button type="button" onClick={() => setAxis("交叉")} style={{ marginLeft: "auto", fontSize: 11.5, color: "#FBBF24", background: "transparent", border: "1px solid rgba(251,191,36,0.32)", borderRadius: 8, padding: "3px 10px", cursor: "pointer" }}>查看全部 →</button>
            </div>
            <div style={{ display: "flex", flexDirection: isMobile ? "column" : "row", flexWrap: isMobile ? "nowrap" : "wrap", gap: 12 }}>
              {crossPicks.map((article) => <button key={article.id} type="button" onClick={() => router.push(`/items/${article.id}`)} style={{ flex: isMobile ? "1 1 auto" : "1 1 260px", minWidth: 0, cursor: "pointer", padding: "14px 16px", textAlign: "left", borderRadius: 14, background: "linear-gradient(145deg,rgba(251,191,36,0.12),rgba(245,158,11,0.04))", border: "1px solid rgba(251,191,36,0.30)", color: "#F2F5FA" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 800, color: "#FBBF24" }}>交叉 {article.crossScore ?? 0}</span>
                  {article.org && <span style={{ fontSize: 11, color: "#828EA3" }}>{article.org}</span>}
                </div>
                <div style={{ marginTop: 7, fontSize: 14.5, fontWeight: 700, lineHeight: 1.4 }}>{article.meta?.titleZh || article.title}</div>
              </button>)}
            </div>
          </div>}

          {view === "精选" && !activeTag && !searchQuery && hotTop.length > 0 && <div>
            <div style={{ display: "flex", gap: 9, margin: "2px 0 10px" }}><span style={{ fontSize: 14, fontWeight: 800, color: "#FDBA74" }}>🔥 当前热点</span><span style={{ fontSize: 11.5, color: "#5E6A82" }}>跨频道 · 48h</span></div>
            <div style={{ display: "flex", flexDirection: isMobile ? "column" : "row", flexWrap: isMobile ? "nowrap" : "wrap", gap: 12 }}>{hotTop.map((article, index) => <button key={article.id} type="button" onClick={() => router.push(`/items/${article.id}`)} style={{ flex: isMobile ? "1 1 auto" : "1 1 260px", minWidth: 0, cursor: "pointer", padding: "14px 16px", textAlign: "left", borderRadius: 14, background: "linear-gradient(145deg,rgba(251,146,60,0.10),rgba(251,113,133,0.04))", border: "1px solid rgba(251,146,60,0.26)", color: "#F2F5FA" }}><span style={{ color: "#FDBA74", fontSize: 12, fontWeight: 800 }}>TOP {index + 1}</span><div style={{ marginTop: 7, fontSize: 14.5, fontWeight: 700 }}>{article.meta?.titleZh || article.title}</div></button>)}</div>
          </div>}

          {articles.map((article, index) => {
            const keyMs = view === "精选" && curatedSort === "最新" ? article.crawledMs : article.timeMs;
            const previous = articles[index - 1];
            const previousMs = previous ? (view === "精选" && curatedSort === "最新" ? previous.crawledMs : previous.timeMs) : undefined;
            const header = showDayHeaders && (index === 0 || dayLabel(previousMs) !== dayLabel(keyMs)) ? dayLabel(keyMs) : null;
            return <React.Fragment key={article.id}>{header && <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "6px 0 -4px" }}><span style={{ fontSize: 12, color: "#94A0B5" }}>{header}</span><span style={{ flex: 1, height: 1, background: "rgba(148,163,184,0.10)" }} /></div>}<ArticleCard article={article} favorited={!!favIds[article.id]} onToggleFav={() => onToggleFav(article)} onTagClick={setActiveTag} read={readIds.has(article.id)} onRead={() => setReadIds(markRead(article.id))} /></React.Fragment>;
          })}

          {hasMore && <button type="button" onClick={() => void loadMore()} disabled={loadingMore} style={{ alignSelf: "center", marginTop: 4, fontSize: 13, fontWeight: 600, color: "#9FD0FF", background: "rgba(59,158,255,0.10)", border: "1px solid rgba(59,158,255,0.22)", padding: "10px 22px", borderRadius: 10, cursor: loadingMore ? "wait" : "pointer" }}>{loadingMore ? "加载中…" : `加载更多（已显示 ${articles.length} / ${total}）`}</button>}
          {error && <button type="button" onClick={() => void loadFirstPage(query)} style={{ alignSelf: "center", border: "1px solid rgba(251,113,133,0.32)", background: "rgba(251,113,133,0.08)", color: "#FCA5A5", borderRadius: 9, padding: "8px 14px", cursor: "pointer" }}>{error}</button>}
          {!loading && !error && articles.length === 0 && <div style={{ padding: "80px 0", textAlign: "center", color: "#6B7689" }}>当前条件下暂无情报</div>}
          {loading && articles.length === 0 && <div style={{ padding: "80px 0", textAlign: "center", color: "#6B7689" }}>正在加载情报…</div>}
        </div>
      </main>
    </div>
  );
}
