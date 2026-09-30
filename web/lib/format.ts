import type { BizLine, Channel, FollowStatus, KnowledgeDomain, KnowledgeType, Stage } from "./types";

export const CHANNELS: { value: Channel; label: string }[] = [
  { value: "tender", label: "招标" },
  { value: "award", label: "中标" },
  { value: "project", label: "项目" },
  { value: "planning", label: "规划" },
  { value: "policy", label: "政策" },
  { value: "market", label: "市场" },
  { value: "company", label: "企业" },
  { value: "tech", label: "技术" },
  { value: "industry", label: "行业" },
];
export const CHANNEL_LABEL = Object.fromEntries(CHANNELS.map((c) => [c.value, c.label])) as Record<Channel, string>;

/** 频道色：商机类用暖色，信息类用冷色，便于扫读时区分。 */
export const CHANNEL_TONE: Record<Channel, string> = {
  tender: "tone-lead",
  award: "tone-lead",
  project: "tone-lead",
  planning: "tone-plan",
  policy: "tone-plan",
  market: "tone-info",
  company: "tone-info",
  tech: "tone-tech",
  industry: "tone-muted",
};

export const STAGE_LABEL: Record<Stage, string> = {
  planning: "规划",
  approval: "核准",
  feasibility: "可研",
  tendering: "招标中",
  awarded: "已中标",
  construction: "在建",
  operation: "投运",
  unknown: "未知",
};

export const BIZ_LABEL: Record<BizLine, string> = {
  inspection_ai: "运检AI",
  grid_epc: "输变电EPC",
  other: "其他",
};

export const DOMAIN_LABEL: Record<KnowledgeDomain, string> = {
  transmission: "输电线路",
  substation: "变电站",
  distribution: "配电网",
  civil: "土建与基础",
  commissioning: "调试试验",
  inspection: "智能运检",
  renewable: "新能源与储能",
  general: "综合",
};

export const KTYPE_LABEL: Record<KnowledgeType, string> = {
  principle: "原理科普",
  construction: "施工工艺",
  standard: "标准规范",
  design: "设计方案",
  safety: "安全与事故",
  cost: "造价定额",
  bidding: "招投标实务",
  management: "项目管理",
  tech: "新技术装备",
};

export const FOLLOW_LABEL: Record<FollowStatus, string> = {
  new: "未处理",
  watching: "关注",
  following: "跟进中",
  ignored: "忽略",
  closed: "已结束",
};

export const TIER_LABEL: Record<string, string> = { T1: "一手", T1_5: "行业", T2: "媒体" };

export const EVAL_MODE_LABEL: Record<string, string> = { stored: "线上判断", rerun: "重跑" };
export const EVAL_SPLIT_LABEL: Record<string, string> = { development: "开发集", holdout: "留出集", all: "全部" };

/** 0–1 的比例显示为百分比；缺值（分母为 0）显示短横。 */
export function formatRatio(v: unknown): string {
  return typeof v === "number" ? `${Math.round(v * 100)}%` : "–";
}

const TZ = "Asia/Shanghai";
const dayKeyFmt = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });
const timeFmt = new Intl.DateTimeFormat("zh-CN", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false });
const weekdayFmt = new Intl.DateTimeFormat("zh-CN", { timeZone: TZ, weekday: "short" });

/** 北京时间的 YYYY-MM-DD。 */
export function dayKey(iso: string | Date): string {
  return dayKeyFmt.format(typeof iso === "string" ? new Date(iso) : iso);
}

export function formatTime(iso: string): string {
  return timeFmt.format(new Date(iso));
}

/** 不依赖运行时 ICU 的中文日期：9月25日 */
function cnDate(key: string): string {
  const [, m, d] = key.split("-");
  return `${Number(m)}月${Number(d)}日`;
}

export function formatDate(iso: string): string {
  return cnDate(dayKey(iso));
}

export function formatDateTime(iso: string): string {
  const key = dayKey(iso);
  return `${key.slice(0, 4)}年${cnDate(key)} ${formatTime(iso)}`;
}

/** 信息流分组标题：今天 / 昨天 / 9月26日 周五 */
export function dayLabel(key: string, now: Date = new Date()): string {
  const today = dayKey(now);
  const yesterday = dayKey(new Date(now.getTime() - 86_400_000));
  if (key === today) return "今天";
  if (key === yesterday) return "昨天";
  const d = new Date(`${key}T12:00:00+08:00`);
  return `${cnDate(key)} ${weekdayFmt.format(d)}`;
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const diff = (now.getTime() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86_400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86_400 * 7) return `${Math.floor(diff / 86_400)} 天前`;
  return formatDate(iso);
}

/** 金额（万元）：≥1 亿显示为亿元。 */
export function formatAmount(wan: string | number | null | undefined): string | null {
  if (wan === null || wan === undefined || wan === "") return null;
  const n = typeof wan === "string" ? Number(wan) : wan;
  if (!Number.isFinite(n)) return null;
  if (n >= 10_000) return `${(n / 10_000).toFixed(n >= 100_000 ? 0 : 2).replace(/\.?0+$/, "")} 亿元`;
  return `${n.toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 万元`;
}

/** 截止倒计时：返回文案与紧急程度。 */
export function deadlineInfo(
  iso: string | null | undefined,
  now: Date = new Date(),
): { text: string; level: "past" | "urgent" | "soon" | "normal" } | null {
  if (!iso) return null;
  const hours = (new Date(iso).getTime() - now.getTime()) / 3_600_000;
  if (hours < 0) return { text: "已截止", level: "past" };
  if (hours < 24) return { text: `${Math.max(1, Math.floor(hours))} 小时后截止`, level: "urgent" };
  const days = Math.floor(hours / 24);
  return { text: `${days} 天后截止`, level: days <= 3 ? "urgent" : days <= 7 ? "soon" : "normal" };
}

export function groupByDay<T extends { first_seen_at: string }>(items: T[]): { key: string; items: T[] }[] {
  const groups: { key: string; items: T[] }[] = [];
  for (const item of items) {
    const key = dayKey(item.first_seen_at);
    const last = groups.at(-1);
    if (last && last.key === key) last.items.push(item);
    else groups.push({ key, items: [item] });
  }
  return groups;
}
