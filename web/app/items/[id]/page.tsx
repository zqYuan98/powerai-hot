import {
  ArrowUpRight,
  Building2,
  ChevronLeft,
  Clock,
  Coins,
  ExternalLink,
  FileText,
  Lightbulb,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { CopySnippet, DetailHeaderActions } from "@/components/feed/DetailTools";
import { DeadlineBadge, ItemCardView } from "@/components/feed/ItemCard";
import { NoteEditor } from "@/components/feed/NoteEditor";
import { StarButton } from "@/components/feed/StarButton";
import { KnowledgeCardView } from "@/components/knowledge/KnowledgeCard";
import { FollowControl } from "@/components/leads/FollowControl";
import { Badge, Card } from "@/components/ui";
import { api } from "@/lib/api.server";
import { cn } from "@/lib/cn";
import {
  BIZ_LABEL,
  CHANNEL_LABEL,
  CHANNEL_TONE,
  formatAmount,
  formatDate,
  formatDateTime,
  STAGE_LABEL,
  TIER_LABEL,
} from "@/lib/format";
import type { ItemDetail, KnowledgeCard, LeadOut } from "@/lib/types";
import { isAdmin } from "@/lib/viewer";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const item = await api<ItemDetail>(`/items/${(await params).id}`);
  return { title: item.title_zh || item.title };
}

const DIMS: { key: keyof ItemDetail["dims"]; label: string }[] = [
  { key: "relevance", label: "电力基建相关" },
  { key: "opportunity", label: "商机价值" },
  { key: "certainty", label: "确定性" },
  { key: "timeliness", label: "时效" },
  { key: "impact", label: "影响面" },
];

function LeadPanel({ itemId, lead, admin }: { itemId: number; lead: LeadOut; admin: boolean }) {
  const dropped = new Set(lead.dropped_fields);
  const amountFormatted = formatAmount(lead.amount_wan);

  return (
    <Card className="overflow-hidden p-5 shadow-card transition-all">
      {/* 头部：标题与跟进控制 */}
      <div className="mb-4 flex items-center justify-between gap-2 border-b border-line/60 pb-3">
        <div className="flex items-center gap-2">
          <span className="inline-block size-2 rounded-full bg-lead" />
          <h2 className="text-sm font-bold tracking-tight text-ink">商机信息</h2>
        </div>
        {admin ? <FollowControl itemId={itemId} status={lead.follow_status} /> : null}
      </div>

      {/* 核心指标看板：金额、截止、阶段 */}
      <div className="mb-4 grid grid-cols-2 gap-2.5">
        {/* 预算金额 */}
        <div className="rounded-lg border border-line/60 bg-surface-2/60 p-3">
          <div className="mb-1 flex items-center justify-between text-xs text-muted">
            <span className="flex items-center gap-1">
              <Coins className="size-3 text-lead" aria-hidden /> 金额
            </span>
            <span className="rounded bg-lead-soft px-1.5 py-0.5 text-[10px] font-semibold text-lead">
              {STAGE_LABEL[lead.stage]}
            </span>
          </div>
          <div className="font-mono text-lg font-bold tracking-tight text-ink">
            {amountFormatted ? (
              <span className="text-lead">{amountFormatted}</span>
            ) : dropped.has("amount_wan") ? (
              <span className="text-xs font-normal text-muted">抽取无法核实已丢弃</span>
            ) : (
              <span className="text-xs font-normal text-muted">原文未披露</span>
            )}
          </div>
        </div>

        {/* 投标截止 */}
        <div className="rounded-lg border border-line/60 bg-surface-2/60 p-3">
          <div className="mb-1 flex items-center justify-between text-xs text-muted">
            <span className="flex items-center gap-1">
              <Clock className="size-3 text-accent" aria-hidden /> 截止
            </span>
            {lead.deadline_at ? <DeadlineBadge iso={lead.deadline_at} /> : null}
          </div>
          <div className="text-xs font-medium text-ink">
            {lead.deadline_at ? (
              <span className="font-mono">{formatDateTime(lead.deadline_at)}</span>
            ) : dropped.has("deadline_at") ? (
              <span className="text-xs font-normal text-muted">抽取无法核实已丢弃</span>
            ) : (
              <span className="text-xs font-normal text-muted">原文未披露</span>
            )}
          </div>
        </div>
      </div>

      {/* 结构化字段清单 */}
      <div className="divide-y divide-line/60 text-xs">
        {/* 项目全称 */}
        <div className="py-2.5">
          <div className="mb-1 text-muted">项目</div>
          <div className="font-medium text-ink leading-relaxed break-words">
            {lead.project_name ?? (
              <span className="text-muted">{dropped.has("project_name") ? "模型抽取结果无法在原文核实，已丢弃" : "原文未披露"}</span>
            )}
          </div>
        </div>

        {/* 招标业主 */}
        <div className="flex items-start justify-between gap-3 py-2.5">
          <span className="w-16 shrink-0 text-muted">业主</span>
          <span className="text-right font-medium text-ink leading-relaxed break-words">
            {lead.owner ?? (
              <span className="text-muted">{dropped.has("owner") ? "模型抽取结果无法在原文核实，已丢弃" : "原文未披露"}</span>
            )}
          </span>
        </div>

        {/* 阶段 */}
        <div className="flex items-center justify-between gap-3 py-2">
          <span className="w-16 shrink-0 text-muted">阶段</span>
          <span className="font-medium text-ink">{STAGE_LABEL[lead.stage]}</span>
        </div>

        {/* 金额行 (保留完整匹配) */}
        <div className="flex items-center justify-between gap-3 py-2">
          <span className="w-16 shrink-0 text-muted">金额</span>
          <span className="font-mono font-medium text-ink">
            {amountFormatted ?? (
              <span className="text-muted">{dropped.has("amount_wan") ? "模型抽取结果无法在原文核实，已丢弃" : "原文未披露"}</span>
            )}
          </span>
        </div>

        {/* 电压等级 */}
        <div className="flex items-center justify-between gap-3 py-2">
          <span className="w-16 shrink-0 text-muted">电压等级</span>
          <span className="font-medium text-ink">
            {lead.voltage_kv ? (
              `${lead.voltage_kv} kV`
            ) : (
              <span className="text-muted">{dropped.has("voltage_kv") ? "模型抽取结果无法在原文核实，已丢弃" : "原文未披露"}</span>
            )}
          </span>
        </div>

        {/* 截止时间行 */}
        <div className="flex items-center justify-between gap-3 py-2">
          <span className="w-16 shrink-0 text-muted">截止</span>
          <span className="text-right font-medium text-ink">
            {lead.deadline_at ? (
              <span className="flex flex-wrap items-center justify-end gap-1.5">
                <span>{formatDateTime(lead.deadline_at)}</span>
                <DeadlineBadge iso={lead.deadline_at} />
              </span>
            ) : (
              <span className="text-muted">{dropped.has("deadline_at") ? "模型抽取结果无法在原文核实，已丢弃" : "原文未披露"}</span>
            )}
          </span>
        </div>

        {/* 招标编号 */}
        <div className="flex items-center justify-between gap-3 py-2">
          <span className="w-16 shrink-0 text-muted">编号</span>
          <div className="flex min-w-0 items-center justify-end gap-1">
            {lead.bid_no ? (
              <>
                <span className="select-all truncate font-mono font-medium text-ink">{lead.bid_no}</span>
                <CopySnippet text={lead.bid_no} label="复制" />
              </>
            ) : (
              <span className="text-muted">{dropped.has("bid_no") ? "模型抽取结果无法在原文核实，已丢弃" : "原文未披露"}</span>
            )}
          </div>
        </div>

        {/* 中标人 */}
        {lead.winner || dropped.has("winner") ? (
          <div className="flex items-start justify-between gap-3 py-2.5">
            <span className="w-16 shrink-0 text-muted">中标人</span>
            <span className="text-right font-medium text-ok leading-relaxed break-words">
              {lead.winner ?? <span className="text-muted">模型抽取结果无法在原文核实，已丢弃</span>}
            </span>
          </div>
        ) : null}

        {/* 业务线与匹配度 */}
        <div className="py-2.5">
          <div className="mb-1 flex items-center justify-between text-muted">
            <span>业务线</span>
            <span className="font-medium text-ink">
              {BIZ_LABEL[lead.biz_line]} · 匹配度 {lead.match_score}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-300",
                lead.match_score >= 80 ? "bg-ok" : lead.match_score >= 50 ? "bg-accent" : "bg-muted/70",
              )}
              style={{ width: `${Math.min(100, Math.max(0, lead.match_score))}%` }}
            />
          </div>
        </div>
      </div>

      {/* 资质要求 */}
      {lead.qualification ? (
        <div className="mt-3 rounded-lg border border-line/70 bg-surface-2/60 p-3">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-ink">
            <ShieldCheck className="size-3.5 text-accent" aria-hidden />
            <span>资质要求</span>
          </div>
          <p className="text-xs leading-relaxed text-ink-2">{lead.qualification}</p>
        </div>
      ) : null}

      {/* 管理员跟进记录 */}
      {admin ? (
        <div className="mt-4 border-t border-line/60 pt-3">
          <NoteEditor
            endpoint={`/leads/${itemId}`}
            field="follow_note"
            initial={lead.follow_note}
            placeholder="跟进记录：联系人、沟通进展、下一步…"
          />
        </div>
      ) : null}
    </Card>
  );
}

export default async function ItemPage({ params }: Props) {
  const id = (await params).id;
  const [item, admin, knowledge] = await Promise.all([
    api<ItemDetail>(`/items/${id}`),
    isAdmin(),
    api<KnowledgeCard[]>("/knowledge/related", { item_id: id }),
  ]);
  const title = item.title_zh || item.title;

  return (
    <div className="space-y-4">
      {/* 顶部导航与快捷操作栏 */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <Link
          href={item.lead ? "/leads" : "/"}
          className="group inline-flex items-center gap-1 font-medium text-muted transition hover:text-ink"
        >
          <ChevronLeft className="size-4 transition group-hover:-translate-x-0.5" aria-hidden />
          <span>返回{item.lead ? "商机" : "列表"}</span>
        </Link>
        <DetailHeaderActions url={item.url} title={title} />
      </div>

      {/* 页面主体两栏布局：优化栅格比例与自适应 */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] xl:grid-cols-[minmax(0,1fr)_380px]">
        {/* 左侧主要内容区 */}
        <article className="min-w-0 space-y-5">
          {/* 文章头部信息卡片 */}
          <div className="rounded-xl border border-line bg-surface p-5 sm:p-6 shadow-card">
            {/* 元信息药丸组 */}
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted">
              <Badge className={cn("font-medium", CHANNEL_TONE[item.channel])}>{CHANNEL_LABEL[item.channel]}</Badge>
              <span className="font-medium text-ink-2">{item.source.name}</span>
              <Badge className="tone-muted">{TIER_LABEL[item.tier] ?? item.tier}</Badge>
              {item.province ? (
                <span className="inline-flex items-center rounded-md bg-surface-2 px-1.5 py-0.5 text-xs text-ink-2">
                  {item.province}
                </span>
              ) : null}
              <span>发现于 {formatDateTime(item.first_seen_at)}</span>
              {item.published_at ? <span>· 发布于 {formatDate(item.published_at)}</span> : null}
            </div>

            {/* 标题与收藏 */}
            <div className="flex items-start justify-between gap-4">
              <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-[26px] sm:leading-snug">{title}</h1>
              <div className="shrink-0 pt-1">
                <StarButton id={item.id} starred={item.starred} />
              </div>
            </div>

            {/* 原题对照 */}
            {item.title_zh && item.title_zh !== item.title ? (
              <div className="mt-3 flex items-start gap-2 rounded-lg border border-line/60 bg-surface-2/40 px-3 py-2 text-xs text-muted">
                <span className="shrink-0 font-medium text-ink-2">原题：</span>
                <span className="min-w-0 flex-1 break-words select-all text-ink-2">{item.title}</span>
                <CopySnippet text={item.title} label="复制原题" />
              </div>
            ) : null}

            {/* 状态异常提示 */}
            {item.status !== "analyzed" ? (
              <p className="mt-3 rounded-md bg-surface-2 px-3 py-2 text-sm text-ink-2">
                状态：{item.status === "screened_out" ? "初筛淘汰" : item.status === "failed" ? "处理失败" : "待处理"}
                {item.status_reason ? `（${item.status_reason}）` : ""}
              </p>
            ) : null}
          </div>

          {/* AI 智能情报研判卡片 */}
          {item.summary ? (
            <div className="relative overflow-hidden rounded-xl border border-line bg-surface p-5 sm:p-6 shadow-card transition-all">
              {/* 顶部微渐变装饰条 */}
              <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-accent via-lead to-accent/30" />

              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex size-6 items-center justify-center rounded-md bg-accent-soft text-accent">
                    <Sparkles className="size-3.5" aria-hidden />
                  </span>
                  <span className="text-sm font-bold tracking-tight text-ink">AI 智能速读研判</span>
                </div>
                <span className="text-[11px] text-muted">自动提炼 · 深度解析</span>
              </div>

              {/* 核心摘要 */}
              <p className="text-[15px] leading-relaxed text-ink font-normal">{item.summary}</p>

              {/* 研判洞察 Callout */}
              {item.reason ? (
                <div className="mt-3.5 flex gap-2.5 rounded-lg border border-lead/25 bg-lead-soft/50 p-3.5 text-sm text-ink-2">
                  <Lightbulb className="mt-0.5 size-4 shrink-0 text-lead" aria-hidden />
                  <div className="space-y-0.5">
                    <span className="block text-xs font-semibold text-lead">研判要点</span>
                    <span className="leading-relaxed">{item.reason}</span>
                  </div>
                </div>
              ) : null}

              {/* 行动建议 Callout */}
              {item.action ? (
                <div className="mt-2.5 flex gap-2.5 rounded-lg border border-accent/25 bg-accent-soft/50 p-3.5 text-sm text-ink">
                  <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
                  <div className="space-y-0.5">
                    <span className="block text-xs font-semibold text-accent">跟进建议</span>
                    <span className="font-medium text-ink leading-relaxed">{item.action}</span>
                  </div>
                </div>
              ) : null}

              {/* 关联标签 */}
              {item.tags.length ? (
                <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-line/60 pt-3">
                  <span className="text-xs text-muted mr-1">关键词：</span>
                  {item.tags.map((t) => (
                    <span
                      key={t}
                      className="rounded-full border border-line/60 bg-surface-2 px-2.5 py-0.5 text-xs text-ink-2 transition hover:bg-surface-2/80"
                    >
                      #{t}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {/* 公文与正文阅读器容器 */}
          <div className="rounded-xl border border-line bg-surface p-5 sm:p-8 shadow-card">
            <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <FileText className="size-4 text-accent" aria-hidden />
                <h2 className="text-base font-bold text-ink">正文</h2>
              </div>
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm font-medium text-accent transition hover:opacity-80"
              >
                <span>查看原文</span>
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            </div>

            {item.content_html ? (
              <div className="prose-article" dangerouslySetInnerHTML={{ __html: item.content_html }} />
            ) : item.content_text ? (
              <div className="prose-article whitespace-pre-line">{item.content_text}</div>
            ) : (
              <div className="py-10 text-center text-sm text-muted">
                该信源只提供标题或摘要（例如详情页有反爬保护），请点击右上角「查看原文」浏览原网内容。
              </div>
            )}
          </div>
        </article>

        {/* 右侧边栏：商机信息、AI 评分、笔记、相关知识 */}
        <aside className="space-y-5 lg:sticky lg:top-20 self-start">
          {item.lead ? <LeadPanel itemId={item.id} lead={item.lead} admin={admin} /> : null}

          {/* AI 评分卡片 */}
          {item.score !== null ? (
            <Card className="p-5 shadow-card">
              <div className="mb-3 flex items-baseline justify-between border-b border-line/60 pb-3">
                <div>
                  <h2 className="text-sm font-bold text-ink">AI 评分</h2>
                  <p className="text-[11px] text-muted">五维综合量化评估</p>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="font-mono text-3xl font-extrabold tracking-tight tabular-nums text-ink">
                    {Math.round(item.score)}
                  </span>
                  <span className="font-mono text-xs text-muted">/ 100</span>
                </div>
              </div>

              {/* 推荐度评级指示 */}
              <div className="mb-3 flex items-center justify-between rounded-md border border-line/60 bg-surface-2/60 px-2.5 py-1.5 text-xs font-medium">
                <span className="text-muted">综合研判评级</span>
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[11px] font-semibold",
                    item.score >= 80
                      ? "bg-ok-soft text-ok"
                      : item.score >= 60
                        ? "bg-accent-soft text-accent"
                        : "bg-surface-2 text-muted",
                  )}
                >
                  {item.score >= 80 ? "高价值商机" : item.score >= 60 ? "值得关注" : "低度相关 / 需甄别"}
                </span>
              </div>

              {/* 细分维度进度条 */}
              <ul className="space-y-2.5">
                {DIMS.map((d) => {
                  const v = item.dims[d.key] ?? 0;
                  return (
                    <li key={d.key} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-muted">{d.label}</span>
                        <span className="font-mono font-medium text-ink tabular-nums">
                          {v} <span className="text-[10px] text-muted">/ 10</span>
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-300",
                            v >= 8 ? "bg-ok" : v >= 5 ? "bg-accent" : "bg-muted/70",
                          )}
                          style={{ width: `${Math.min(100, v * 10)}%` }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>

              {item.selected ? (
                <div className="mt-3 flex items-center gap-1.5 border-t border-line/60 pt-3 text-xs font-medium text-ok">
                  <span className="inline-block size-1.5 rounded-full bg-ok" />
                  已收录进精选情报
                </div>
              ) : null}
            </Card>
          ) : null}

          {/* 相关知识 */}
          {knowledge.length ? (
            <Card className="p-5 shadow-card">
              <h2 className="text-sm font-bold text-ink">相关知识</h2>
              <p className="mb-2 text-xs text-muted">知识库里与这条内容相关的工艺、规范与方案</p>
              <div className="divide-y divide-line/60">
                {knowledge.map((k) => (
                  <KnowledgeCardView key={k.id} k={k} compact />
                ))}
              </div>
            </Card>
          ) : null}

          {/* 笔记（仅管理员可见） */}
          {admin ? (
            <Card className="p-5 shadow-card">
              <h2 className="mb-2 text-sm font-bold text-ink">笔记</h2>
              <NoteEditor endpoint={`/items/${item.id}`} field="note" initial={item.note} placeholder="记下你的判断…" />
            </Card>
          ) : null}

          {/* 同一事件的其他报道 */}
          {item.story && item.related.length ? (
            <Card className="p-5 shadow-card">
              <h2 className="text-sm font-bold text-ink">同一事件的其他报道</h2>
              <Link href={`/stories/${item.story.id}`} className="mt-1 block text-xs text-accent hover:underline">
                查看事件时间线（{item.story.item_count} 条 · {item.story.source_count} 家信源）→
              </Link>
              <div className="mt-2 divide-y divide-line/60">
                {item.related.slice(0, 5).map((r) => (
                  <ItemCardView key={r.id} item={r} showDate inStory />
                ))}
              </div>
            </Card>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
