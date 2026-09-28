import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Card, Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/api.server";
import { CHANNEL_LABEL, CHANNEL_TONE, relativeTime } from "@/lib/format";
import type { HotStory } from "@/lib/types";

export const metadata: Metadata = { title: "热点" };

export default async function HotPage() {
  const stories = await api<HotStory[]>("/hot", { hours: 48, limit: 10 });
  return (
    <>
      <PageHeader
        title="热点"
        desc="过去 48 小时被最多独立信源报道的事件。热度 = 独立来源数 × 24 小时半衰期，只反映讨论度，不代表商机价值。"
      />
      {stories.length === 0 ? (
        <Empty title="暂无热点">同一事件被两家以上信源报道后会出现在这里。</Empty>
      ) : (
        <ol className="space-y-3">
          {stories.map((s) => {
            const item = s.lead_item;
            const top = s.rank <= 3;
            return (
              <li key={s.story.id}>
                <Card className="relative flex gap-4 p-4">
                  <span
                    className={
                      top
                        ? "font-mono text-2xl leading-none font-semibold text-lead tabular-nums"
                        : "font-mono text-lg leading-none text-muted tabular-nums"
                    }
                  >
                    {s.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                      <Badge className={CHANNEL_TONE[item.channel]}>{CHANNEL_LABEL[item.channel]}</Badge>
                      {s.is_new ? <Badge className="tone-lead">新</Badge> : null}
                      <span>{s.story.source_count} 家信源</span>
                      <span>最近 {relativeTime(s.last_seen_at)}</span>
                    </div>
                    <Link
                      href={`/stories/${s.story.id}`}
                      className={`font-semibold text-ink after:absolute after:inset-0 hover:text-accent ${top ? "text-lg" : ""}`}
                    >
                      {s.story.title}
                    </Link>
                    {top && item.summary ? <p className="mt-1.5 line-clamp-2 text-sm text-ink-2">{item.summary}</p> : null}
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm font-semibold text-ink tabular-nums">{s.story.heat.toFixed(1)}</div>
                    <div className="text-[11px] text-muted">热度</div>
                  </div>
                </Card>
              </li>
            );
          })}
        </ol>
      )}
    </>
  );
}
