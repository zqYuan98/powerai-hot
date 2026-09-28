import { ArrowUpRight, Lightbulb } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  CHANNEL_LABEL,
  CHANNEL_TONE,
  deadlineInfo,
  formatAmount,
  formatDate,
  formatTime,
  STAGE_LABEL,
  TIER_LABEL,
} from "@/lib/format";
import type { ItemCard as Item, LeadOut } from "@/lib/types";

import { StarButton } from "./StarButton";

export function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const tone = score >= 80 ? "text-lead" : score >= 60 ? "text-ink-2" : "text-muted";
  return (
    <span className={cn("font-mono text-xs tabular-nums", tone)} title="AI 评分（0–100）">
      {Math.round(score)}
    </span>
  );
}

export function DeadlineBadge({ iso }: { iso: string | null | undefined }) {
  const info = deadlineInfo(iso);
  if (!info) return null;
  const tone = {
    past: "text-muted bg-surface-2",
    urgent: "text-danger bg-danger-soft",
    soon: "text-lead bg-lead-soft",
    normal: "text-ink-2 bg-surface-2",
  }[info.level];
  return <Badge className={tone}>{info.text}</Badge>;
}

/** 商机关键字段一行：阶段 · 金额 · 电压 · 业主 · 截止 */
export function LeadFacts({ lead, className }: { lead: LeadOut; className?: string }) {
  const amount = formatAmount(lead.amount_wan);
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-2", className)}>
      {lead.stage !== "unknown" ? <Badge className="tone-lead">{STAGE_LABEL[lead.stage]}</Badge> : null}
      {amount ? <span className="font-medium text-ink">{amount}</span> : null}
      {lead.voltage_kv ? <span>{lead.voltage_kv}kV</span> : null}
      {lead.owner ? <span className="max-w-[16em] truncate">业主：{lead.owner}</span> : null}
      {lead.winner ? <span className="max-w-[16em] truncate">中标：{lead.winner}</span> : null}
      <DeadlineBadge iso={lead.deadline_at} />
    </div>
  );
}

export function ItemCardView({
  item,
  showDate = false,
  inStory = false,
}: {
  item: Item;
  showDate?: boolean;
  /** 已在事件上下文中（事件时间线、同事件报道），不再显示「另有 N 家」 */
  inStory?: boolean;
}) {
  const title = item.title_zh || item.title;
  return (
    <article className={cn("group relative py-4", item.read && "opacity-75")}>
      <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <time dateTime={item.first_seen_at} className="tabular-nums">
          {showDate ? `${formatDate(item.first_seen_at)} ` : ""}
          {formatTime(item.first_seen_at)}
        </time>
        <span className="text-ink-2">{item.source.name}</span>
        {item.tier === "T1" ? <Badge className="tone-info">{TIER_LABEL.T1}</Badge> : null}
        <Badge className={CHANNEL_TONE[item.channel]}>{CHANNEL_LABEL[item.channel]}</Badge>
        {item.province ? <span>{item.province}</span> : null}
        <span className="ml-auto flex items-center gap-2">
          <ScoreBadge score={item.score} />
          <StarButton id={item.id} starred={item.starred} />
        </span>
      </div>

      <h2 className="text-[16px] leading-snug font-semibold text-ink">
        <Link href={`/items/${item.id}`} className="after:absolute after:inset-0 hover:text-accent">
          {title}
        </Link>
      </h2>
      {item.title_zh && item.title_zh !== item.title ? (
        <p className="mt-0.5 line-clamp-1 text-xs text-muted">原题：{item.title}</p>
      ) : null}

      {item.lead ? <LeadFacts lead={item.lead} className="mt-2" /> : null}
      {item.summary ? <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-ink-2">{item.summary}</p> : null}

      {item.reason || item.action ? (
        <div className="mt-2 space-y-1 text-[13px]">
          {item.reason ? (
            <p className="flex gap-1.5 text-ink-2">
              <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-lead" aria-hidden />
              <span>{item.reason}</span>
            </p>
          ) : null}
          {item.action ? (
            <p className="flex gap-1.5 font-medium text-accent">
              <ArrowUpRight className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span>{item.action}</span>
            </p>
          ) : null}
        </div>
      ) : null}

      {!inStory && item.also_reported > 0 && item.story_id ? (
        <Link
          href={`/stories/${item.story_id}`}
          className="relative z-10 mt-2 inline-block text-xs text-muted underline-offset-2 hover:text-accent hover:underline"
        >
          另有 {item.also_reported} 家信源报道 →
        </Link>
      ) : null}
    </article>
  );
}
