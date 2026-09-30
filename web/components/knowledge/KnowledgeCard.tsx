import { Sparkles } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui";
import { cn } from "@/lib/cn";
import { DOMAIN_LABEL, formatDate, KTYPE_LABEL } from "@/lib/format";
import type { KnowledgeCard } from "@/lib/types";

const STATUS_LABEL: Record<KnowledgeCard["status"], string> = {
  new: "待处理",
  analyzed: "已展示",
  rejected: "未通过",
  duplicate: "重复",
  hidden: "已隐藏",
  failed: "失败",
};

export function KnowledgeMeta({ k, className }: { k: KnowledgeCard; className?: string }) {
  const classified = k.status !== "new" && k.status !== "failed"; // 还没分析的分类是默认值，不显示
  return (
    <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted", className)}>
      {classified ? <Badge className="tone-info">{DOMAIN_LABEL[k.domain]}</Badge> : null}
      {classified ? <Badge className="tone-muted">{KTYPE_LABEL[k.ktype]}</Badge> : null}
      {k.account ? <span className="text-ink-2">{k.account}</span> : null}
      {k.published_at ? <span>{formatDate(k.published_at)}</span> : null}
      {k.featured ? (
        <span className="inline-flex items-center gap-0.5 text-lead">
          <Sparkles className="size-3" aria-hidden />
          精选
        </span>
      ) : null}
      {k.status !== "analyzed" ? <Badge className="tone-lead">{STATUS_LABEL[k.status]}</Badge> : null}
    </div>
  );
}

/** 知识卡片（列表项）：标题 + 一句话 + 前三条要点 + 涉及标准。 */
export function KnowledgeCardView({ k, compact = false }: { k: KnowledgeCard; compact?: boolean }) {
  return (
    <article className="group relative py-4">
      <KnowledgeMeta k={k} className="mb-1.5" />
      <h2 className={cn("leading-snug font-semibold text-ink", compact ? "text-sm" : "text-[16px]")}>
        <Link href={`/knowledge/${k.id}`} className="after:absolute after:inset-0 hover:text-accent">
          {k.title}
        </Link>
      </h2>
      {k.status_reason && !compact ? <p className="mt-1 text-xs text-lead">{k.status_reason}</p> : null}
      {k.summary && !compact ? <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{k.summary}</p> : null}
      {k.key_points.length && !compact ? (
        <ul className="mt-2 space-y-1 text-[13px] text-ink-2">
          {k.key_points.slice(0, 3).map((p) => (
            <li key={p} className="flex gap-2">
              <span className="mt-[0.55em] size-1 shrink-0 rounded-full bg-accent" aria-hidden />
              <span className="line-clamp-2">{p}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {k.standards.length && !compact ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {k.standards.slice(0, 4).map((s) => (
            <span key={s} className="rounded border border-line px-1.5 py-px font-mono text-[11px] text-muted">
              {s}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}
