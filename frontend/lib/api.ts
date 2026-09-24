import type { SourceReport, SourceType } from "./types";

const BASE = "/api";

let authEpoch = 0;

export function advanceAuthEpoch(): number {
  authEpoch += 1;
  return authEpoch;
}

export function getAuthEpoch(): number {
  return authEpoch;
}

export const getCurrentAuthEpoch = getAuthEpoch;
export const currentAuthEpoch = getAuthEpoch;

type UnauthorizedListener = (epoch: number) => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();

export function subscribeUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

export const onUnauthorized = subscribeUnauthorized;

function notifyUnauthorized(epoch: number): void {
  for (const listener of [...unauthorizedListeners]) {
    try { listener(epoch); } catch { /* listeners cannot block the original API error */ }
  }
}

export interface SessionPayload {
  authenticated: boolean;
  role: "workspace" | "admin" | null;
  mode: string | null;
  workspace: { name: string; subtitle: string };
}

export interface ArticleQuery {
  channel?: string;
  threadId?: number;
  q?: string;
  kind?: string;
  minScore?: number;
  view?: "curated" | "all" | "noise";
  window?: "24h" | "7d" | "all";
  tag?: string;
  axis?: "交叉" | "AI" | "行业" | "弱";
  sort?: "score" | "latest";
  limit?: number;
  cursor?: string;
  includeAll?: boolean;
}

export interface AxisMonitorOut {
  by_axis: { axis: string; count: number; curated: number; avg_cross: number; avg_quality: number }[];
  by_source: { source: string; tier: string; count: number; cross: number; ai: number; power: number; avg_cross: number }[];
  trend: { day: string; cross: number; ai: number; power: number; weak: number }[];
  power_supply_ratio: number;
  // 只描述 trend 的跨度；by_axis / by_source / power_supply_ratio 都是全量
  trend_window_days: number;
}

export interface ArticlePageRaw {
  items: any[];
  next_cursor: string | null;
  has_more: boolean;
  total: number;
}

export interface ArticleFreshness {
  latest_crawled_at: string | null;
  added_24h: number;
  curated_24h: number;
}

export interface ArticleTimelineOut {
  latest_crawled_at: string | null;
  buckets: Array<{ ts: string; count: number; curated: number }>;
}

function articleQueryString(query: ArticleQuery = {}, includeChannel = true): string {
  const params = new URLSearchParams();
  if (includeChannel && query.channel) params.set("channel", query.channel);
  if (query.threadId !== undefined) params.set("thread_id", String(query.threadId));
  if (query.q?.trim()) params.set("q", query.q.trim());
  if (query.kind) params.set("kind", query.kind);
  if (query.minScore !== undefined) params.set("min_score", String(query.minScore));
  if (query.view) params.set("view", query.view);
  if (query.window) params.set("window", query.window);
  if (query.tag?.trim()) params.set("tag", query.tag.trim());
  if (query.axis) params.set("axis", query.axis);
  if (query.sort) params.set("sort", query.sort);
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  if (query.cursor) params.set("cursor", query.cursor);
  if (query.includeAll) params.set("include_all", "true");
  const value = params.toString();
  return value ? `?${value}` : "";
}

export class ApiError extends Error {
  readonly status: number;
  readonly body?: unknown;

  constructor(status: number, path: string, body?: unknown) {
    super(`API ${path} -> ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export type SourceStatus = SourceReport["status"];
// Authentication is established by the same-origin HttpOnly session cookie.

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const requestEpoch = path.startsWith("/auth/session") ? undefined : getAuthEpoch();
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    ...init,
    credentials: "same-origin",
    headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
  });
  if (res.status === 401 && requestEpoch !== undefined) notifyUnauthorized(requestEpoch);
  if (!res.ok) {
    const body = await res.text();
    let parsed: unknown = body;
    try { parsed = body ? JSON.parse(body) : undefined; } catch { /* keep text */ }
    throw new ApiError(res.status, path, parsed);
  }
  // 204 No Content（如 DELETE /sources/{id}）等空响应体上 res.json() 会抛错
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  getSession: () => http<SessionPayload>("/auth/session"),
  createSession: (scope: "workspace" | "admin", token: string) =>
    http<SessionPayload>("/auth/session", { method: "POST", body: JSON.stringify({ scope, token }) }),
  deleteSession: () => http<void>("/auth/session", { method: "DELETE" }),
  listArticles: (query: ArticleQuery = {}) =>
    http<ArticlePageRaw>(`/articles${articleQueryString(query)}`),
  threadSummary: () => http<Array<{ id: number | null; name: string; count: number }>>("/threads/summary"),
  articleChannels: (query: ArticleQuery = {}) => {
    const filters = { ...query };
    delete filters.channel;
    delete filters.threadId;
    delete filters.cursor;
    delete filters.limit;
    delete filters.includeAll;
    return http<Array<{ name: string; count: number }>>(`/articles/channels${articleQueryString(filters, false)}`);
  },
  articleFreshness: () => http<ArticleFreshness>("/articles/freshness"),
  axisMonitor: (days = 7) => http<AxisMonitorOut>(`/admin/axis?days=${days}`),
  articleTimeline: (hours = 48) => http<ArticleTimelineOut>(`/articles/timeline?hours=${hours}`),
  articleHotspots: (limit = 2) => http<any[]>(`/articles/hotspots?limit=${limit}`),
  articleCrossPicks: (limit = 4) => http<any[]>(`/articles/cross-picks?limit=${limit}`),
  getArticle: (id: number | string) => http<any>(`/articles/${id}`),
  listSources: (mine = false) => http<SourceRow[]>(`/sources${mine ? "?mine=true" : ""}`),
  submitSourceSubmission: (body: { name: string; url: string; type: SourceType; reason?: string }) =>
    http<SourceRow>("/sources/submissions", { method: "POST", body: JSON.stringify(body) }),
  listSourceSubmissions: () => http<SourceRow[]>("/sources/submissions"),
  addSource: (body: { name: string; url: string; type: string; reason?: string }, active = false) =>
    http<any>(`/sources?active=${active}`, { method: "POST", body: JSON.stringify(body) }),
  setSourceStatus: (id: number, status: string) =>
    http<any>(`/sources/${id}/status?status=${encodeURIComponent(status)}`, { method: "POST", body: "{}" }),
  deleteSource: (id: number) => http<void>(`/sources/${id}`, { method: "DELETE" }),
  importOpml: (opml: string, active = false) =>
    http<{ imported: number; skipped: number; errors: string[] }>("/sources/import-opml", {
      method: "POST", body: JSON.stringify({ opml, active }),
    }),
  // 立即采集：异步启动（全信源+逐条打分需数分钟，同步等待会撞代理超时），用 crawlStatus 轮询进度
  crawlNow: (limit = 15) =>
    http<{ status: string; started_at?: string | null }>("/admin/crawl", {
      method: "POST", body: JSON.stringify({ limit }),
    }),
  crawlStatus: () => http<CrawlStatus>("/admin/crawl/status"),
  // 流水线全景状态：定时监控 + 手动采集 + 入库节奏 + 信源健康 + 日报新鲜度（一次取齐）
  pipelineStatus: () => http<PipelineStatus>("/admin/pipeline"),
  systemStatus: () => http<SystemStatus>("/system/status"),
  knowledgeItem: (slug: string) => http<any>(`/knowledge/items/${slug}`),
  graph: () => http<any>("/knowledge/graph"),
  getSubscription: () => http<any>("/subscriptions"),
  updateSubscription: (body: unknown) =>
    http<any>("/subscriptions", { method: "PUT", body: JSON.stringify(body) }),
  subscriptionHits: (limit = 3) =>
    http<Array<{ article: any; keyword: string }>>(`/subscriptions/hits?limit=${limit}`),

  // 管理后台
  getAdminConfig: () => http<AdminConfig>("/admin/config"),
  setProvider: (provider: string, taskProviders?: Record<string, string>) =>
    http<AdminConfig>("/admin/config", {
      method: "PUT",
      body: JSON.stringify({ provider, task_providers: taskProviders }),
    }),
  testModel: () => http<{ provider: string; result: string }>("/admin/test", { method: "POST", body: "{}" }),

  // 收藏 / 知识卡片
  listFavorites: () => http<number[]>("/favorites"),
  addFavorite: (id: number) => http<any>(`/favorites/${id}`, { method: "POST", body: "{}" }),
  removeFavorite: (id: number) => http<any>(`/favorites/${id}`, { method: "DELETE" }),
  listCards: (category?: string, q?: string) => {
    const p = new URLSearchParams();
    if (category) p.set("category", category);
    if (q) p.set("q", q);
    const qs = p.toString();
    return http<CardOut[]>(`/cards${qs ? `?${qs}` : ""}`);
  },
  patchCard: (id: number, body: { note?: string; category?: string }) =>
    http<CardOut>(`/cards/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  retryCard: (id: number) => http<any>(`/cards/${id}/retry`, { method: "POST", body: "{}" }),

  // 评分配置
  getScoring: () => http<any>("/admin/scoring"),
  putScoring: (body: any) => http<any>("/admin/scoring", { method: "PUT", body: JSON.stringify(body) }),
  recomputeScoring: () => http<{ recomputed: number }>("/admin/scoring/recompute", { method: "POST", body: "{}" }),

  // 周报 / 主题研报
  createTopicReport: (topic: string) =>
    http<{ id: number; title: string; status: string }>("/reports/topic", { method: "POST", body: JSON.stringify({ topic }) }),
  retryReport: (id: number) => http<any>(`/reports/${id}/retry`, { method: "POST", body: "{}" }),
  weeklyNow: () => http<{ id: number; title: string; status: string }>("/admin/weekly", { method: "POST", body: "{}" }),

  // 今日精选 / 事件簇
  listReports: (type?: string) => http<ReportSummary[]>(`/reports${type ? `?type=${type}` : ""}`),
  getReport: (id: number) => http<ReportDetail>(`/reports/${id}`),
  digestNow: () => http<{ id: number; title: string; total: number }>("/admin/digest", { method: "POST", body: "{}" }),
  getClusterArticles: (id: number) => http<any[]>(`/articles/${id}/cluster`),
};

// 后端 SourceOut 的前端镜像（backend/api/dto.py）
export interface SourceRow {
  id: number;
  name: string;
  url: string;
  type: SourceType;
  status: SourceStatus;
  submitted_by?: string | null;
  tier?: string | null; // T1 | T1.5 | T2
  last_status?: string | null; // ok | error | null(从未抓取)
  last_error?: string | null;
  last_crawled_at?: string | null;
  builtin?: boolean;   // 代码内置采集器（后端计算，见 backend/api/sources.py::_to_out）
  crawlable?: boolean; // 已采纳后是否实际参与抓取
  // 产出价值（/admin/sources/health 提供）：判断信源该留该砍的依据
  article_count?: number;
  noise_pct?: number;
  curated_count?: number;
  power_count?: number;
}

export interface CardOut {
  id: number; article_id: number; category: string;
  problem?: string | null; method?: string | null; conclusion?: string | null;
  power_relevance?: string | null; note?: string | null; status: string; created_at?: string;
  article?: { title: string; url?: string; channel: string; kind: string; title_zh?: string | null } | null;
}

export interface ReportSummary {
  id: number; type: string; title: string; status: string;
  total?: number; period_start?: string; period_end?: string; created_at?: string;
}
export interface ReportDetail extends ReportSummary {
  content_md?: string | null;
  sections: { name: string; articles: any[] }[];
}

export interface CrawlStatus {
  status: "idle" | "running" | "done" | "error";
  stats?: CrawlResult | null;
  error?: string | null;
  started_at?: string | null;
}

export interface PipelineStatus {
  server_time: string;
  monitor: {
    enabled: boolean;
    interval_hours: number;
    running: boolean;
    last_run: (Partial<CrawlResult> & { at?: string; error?: string }) | null;
    next_runs: Record<string, string>; // crawl/papers/digest/weekly → 本地时区 ISO
  };
  manual_crawl: CrawlStatus & { group?: string | null };
  articles: {
    total: number;
    added_24h: number;
    curated_24h: number;
    noise_24h: number;
    last_crawled_at: string | null; // UTC naive
    unscored_backlog: number;
  };
  sources: {
    ok: number;
    error: number;
    never: number;
    errors: { name: string; error: string; at: string | null }[];
    blocked: { name: string; reason: string }[];
  };
  digest: { title: string; total: number; created_at: string | null } | null;
}

export interface SystemStatus {
  server_time: string;
  latest_jobs: Array<{
    run_key: string;
    job_name: string;
    status: "running" | "ok" | "degraded" | "failed" | "skipped";
    started_at: string | null;
    finished_at: string | null;
    fetched: number;
    inserted: number;
    selected: number;
    source_failures: number;
  }>;
  freshness: { latest_ingested_at: string | null; added_24h: number };
  degradation: { processed: number; fallback_or_rule: number; ratio: number };
  failed_sources: Array<{ name: string; transport_status: string; parse_status: string; error_summary: string | null }>;
}

export interface CrawlResult {
  group: string;
  provider: string;
  fetched: number;
  inserted: number;
  curated: number;
  skipped_duplicate: number;
  prefiltered_out: number;
  analyze_errors: number;
  collector_errors: string[];
  rescored?: number;        // 本轮补打分成功的积压条数
  rescore_backlog?: number; // 剩余未打分积压
  samples: { title: string; score: number; channel: string }[];
}

export interface AdminConfig {
  provider: string;
  valid_providers: string[];
  task_providers: Record<string, string>;
  usage: Record<string, { calls: number; tokens: number }>;
  estimated_cost_cny: Record<string, number>;
  price_per_1k_cny: Record<string, number>;
}

// ---- 后端 DTO → 前端类型映射 ----
import { Article } from "./types";

const ACCENT_BY_ORG: Record<string, Article["accent"]> = {
  国家电网: "blue", 浙江电力: "blue", 南方电网: "green", 国家能源局: "green",
};

// 后端时间戳为 UTC naive、序列化不带时区标记——补 Z 按 UTC 解析
function toMs(iso?: string | null): number | undefined {
  if (!iso) return undefined;
  const d = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z");
  return isNaN(d.getTime()) ? undefined : d.getTime();
}

// 相对时间标签：口径统一的"N 分钟/小时/天前"，超一周退回具体日期
function relLabel(ms?: number): string | undefined {
  if (!ms) return undefined;
  const diff = Date.now() - ms;
  if (diff < 0) return undefined;  // 源侧时钟超前，别显示"-3 小时前"
  const h = diff / 36e5;
  if (h < 1) return `${Math.max(1, Math.floor(diff / 6e4))} 分钟前`;
  if (h < 24) return `${Math.floor(h)} 小时前`;
  const days = Math.floor(h / 24);
  if (days <= 7) return `${days} 天前`;
  const d = new Date(ms);
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

export function mapArticle(d: any): Article {
  const accent: Article["accent"] =
    d.channel === "AI洞察" ? "violet" : d.channel === "招标公告" ? "amber" : ACCENT_BY_ORG[d.org] ?? "blue";
  return {
    id: d.id,
    title: d.title,
    summary: d.summary ?? "",
    tags: d.tags ?? [],
    channel: d.channel,
    org: d.org,
    hot: d.hot,
    deadlineDays: d.deadline_days,
    sourceDomain: d.source_domain,
    url: d.url,
    publishedLabel: d.published_label,
    viewCount: d.view_count,
    relevanceScore: d.relevance_score,
    recommendReason: d.recommend_reason,
    curated: d.curated,
    kind: d.kind,
    meta: d.meta
      ? {
          authors: d.meta.authors,
          arxivId: d.meta.arxiv_id,
          pdfUrl: d.meta.pdf_url,
          hfUrl: d.meta.hf_url,
          titleZh: d.meta.title_zh,
        }
      : undefined,
    contentHtml: d.content_html ?? null,
    clusterId: d.cluster_id,
    relatedCount: d.related_count ?? 0,
    primaryThreadId: d.primary_thread_id ?? null,
    threadAffinity: d.thread_affinity ?? undefined,
    scored: d.scored,
    processingStatus: d.processing_status,
    scoredBy: d.scored_by,
    noiseReason: d.noise_reason,
    timeMs: toMs(d.published_at) ?? toMs(d.crawled_at),
    timeLabel: relLabel(toMs(d.published_at) ?? toMs(d.crawled_at)),
    crawledMs: toMs(d.crawled_at),
    tier: d.tier,
    crossScore: d.cross_score,
    axis: d.axis,
    accent,
  };
}
