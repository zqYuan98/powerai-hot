import { ArrowUpRight, ExternalLink, Lightbulb } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { DeadlineBadge, ItemCardView } from "@/components/feed/ItemCard";
import { NoteEditor } from "@/components/feed/NoteEditor";
import { StarButton } from "@/components/feed/StarButton";
import { KnowledgeCardView } from "@/components/knowledge/KnowledgeCard";
import { FollowControl } from "@/components/leads/FollowControl";
import { Badge, Card } from "@/components/ui";
import { api } from "@/lib/api.server";
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

function Row({ label, value, dropped }: { label: string; value: ReactNode; dropped?: boolean }) {
  return (
    <div className="flex gap-3 py-1.5 text-sm">
      <dt className="w-20 shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">
        {value ?? <span className="text-muted">{dropped ? "模型抽取结果无法在原文核实，已丢弃" : "原文未披露"}</span>}
      </dd>
    </div>
  );
}

function LeadPanel({ itemId, lead, admin }: { itemId: number; lead: LeadOut; admin: boolean }) {
  const dropped = new Set(lead.dropped_fields);
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">商机信息</h2>
        {admin ? <FollowControl itemId={itemId} status={lead.follow_status} /> : null}
      </div>
      <dl className="divide-y divide-line">
        <Row label="项目" value={lead.project_name} dropped={dropped.has("project_name")} />
        <Row label="业主" value={lead.owner} dropped={dropped.has("owner")} />
        <Row label="阶段" value={STAGE_LABEL[lead.stage]} />
        <Row label="金额" value={formatAmount(lead.amount_wan)} dropped={dropped.has("amount_wan")} />
        <Row label="电压等级" value={lead.voltage_kv ? `${lead.voltage_kv} kV` : null} dropped={dropped.has("voltage_kv")} />
        <Row
          label="截止"
          value={
            lead.deadline_at ? (
              <span className="flex flex-wrap items-center gap-2">
                {formatDateTime(lead.deadline_at)} <DeadlineBadge iso={lead.deadline_at} />
              </span>
            ) : null
          }
          dropped={dropped.has("deadline_at")}
        />
        <Row label="编号" value={lead.bid_no} dropped={dropped.has("bid_no")} />
        {lead.winner || dropped.has("winner") ? <Row label="中标人" value={lead.winner} dropped={dropped.has("winner")} /> : null}
        {lead.qualification ? <Row label="资质要求" value={lead.qualification} /> : null}
        <Row label="业务线" value={`${BIZ_LABEL[lead.biz_line]} · 匹配度 ${lead.match_score}`} />
      </dl>
      {admin ? (
        <div className="mt-3">
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
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <article className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted">
          <Badge className={CHANNEL_TONE[item.channel]}>{CHANNEL_LABEL[item.channel]}</Badge>
          <span className="text-ink-2">{item.source.name}</span>
          <Badge className="tone-muted">{TIER_LABEL[item.tier] ?? item.tier}</Badge>
          {item.province ? <span>{item.province}</span> : null}
          <span>发现于 {formatDateTime(item.first_seen_at)}</span>
          {item.published_at ? <span>发布 {formatDate(item.published_at)}</span> : null}
        </div>
        <div className="flex items-start gap-3">
          <h1 className="flex-1 text-2xl leading-snug font-semibold tracking-tight text-ink">{title}</h1>
          <StarButton id={item.id} starred={item.starred} />
        </div>
        {item.title_zh && item.title_zh !== item.title ? <p className="mt-1 text-sm text-muted">原题：{item.title}</p> : null}

        {item.status !== "analyzed" ? (
          <p className="mt-3 rounded-md bg-surface-2 px-3 py-2 text-sm text-ink-2">
            状态：{item.status === "screened_out" ? "初筛淘汰" : item.status === "failed" ? "处理失败" : "待处理"}
            {item.status_reason ? `（${item.status_reason}）` : ""}
          </p>
        ) : null}

        {item.summary ? (
          <Card className="mt-4 p-4">
            <p className="leading-relaxed text-ink">{item.summary}</p>
            {item.reason ? (
              <p className="mt-3 flex gap-1.5 text-sm text-ink-2">
                <Lightbulb className="mt-0.5 size-4 shrink-0 text-lead" aria-hidden />
                {item.reason}
              </p>
            ) : null}
            {item.action ? (
              <p className="mt-1.5 flex gap-1.5 text-sm font-medium text-accent">
                <ArrowUpRight className="mt-0.5 size-4 shrink-0" aria-hidden />
                {item.action}
              </p>
            ) : null}
            {item.tags.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {item.tags.map((t) => (
                  <Badge key={t} className="tone-muted">
                    {t}
                  </Badge>
                ))}
              </div>
            ) : null}
          </Card>
        ) : null}

        <div className="mt-6">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">正文</h2>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-sm text-accent hover:underline"
            >
              查看原文 <ExternalLink className="size-3.5" aria-hidden />
            </a>
          </div>
          {item.content_html ? (
            <div className="prose-article" dangerouslySetInnerHTML={{ __html: item.content_html }} />
          ) : item.content_text ? (
            <div className="prose-article whitespace-pre-line">{item.content_text}</div>
          ) : (
            <p className="text-sm text-muted">该信源只提供标题（例如详情页有反爬），请查看原文。</p>
          )}
        </div>
      </article>

      <aside className="space-y-4">
        {item.lead ? <LeadPanel itemId={item.id} lead={item.lead} admin={admin} /> : null}

        {item.score !== null ? (
          <Card className="p-4">
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold text-ink">AI 评分</h2>
              <span className="font-mono text-lg font-semibold text-ink tabular-nums">{Math.round(item.score)}</span>
            </div>
            <ul className="space-y-1.5">
              {DIMS.map((d) => {
                const v = item.dims[d.key] ?? 0;
                return (
                  <li key={d.key} className="flex items-center gap-2 text-xs">
                    <span className="w-20 shrink-0 text-muted">{d.label}</span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                      <span className="block h-full rounded-full bg-accent" style={{ width: `${v * 10}%` }} />
                    </span>
                    <span className="w-5 text-right font-mono text-ink-2 tabular-nums">{v}</span>
                  </li>
                );
              })}
            </ul>
            {item.selected ? <p className="mt-2 text-xs text-ok">已进入精选</p> : null}
          </Card>
        ) : null}

        {knowledge.length ? (
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-ink">相关知识</h2>
            <p className="text-xs text-muted">知识库里与这条内容相关的工艺、规范与方案</p>
            <div className="mt-1 divide-y divide-line">
              {knowledge.map((k) => (
                <KnowledgeCardView key={k.id} k={k} compact />
              ))}
            </div>
          </Card>
        ) : null}

        {admin ? (
          <Card className="p-4">
            <h2 className="mb-2 text-sm font-semibold text-ink">笔记</h2>
            <NoteEditor endpoint={`/items/${item.id}`} field="note" initial={item.note} placeholder="记下你的判断…" />
          </Card>
        ) : null}

        {item.story && item.related.length ? (
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-ink">同一事件的其他报道</h2>
            <Link href={`/stories/${item.story.id}`} className="text-xs text-accent hover:underline">
              查看事件时间线（{item.story.item_count} 条 · {item.story.source_count} 家信源）→
            </Link>
            <div className="mt-1 divide-y divide-line">
              {item.related.slice(0, 5).map((r) => (
                <ItemCardView key={r.id} item={r} showDate inStory />
              ))}
            </div>
          </Card>
        ) : null}
      </aside>
    </div>
  );
}
