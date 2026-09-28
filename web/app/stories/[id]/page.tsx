import type { Metadata } from "next";

import { ItemCardView } from "@/components/feed/ItemCard";
import { Card, PageHeader } from "@/components/ui";
import { api } from "@/lib/api.server";
import { formatDateTime } from "@/lib/format";
import type { StoryDetail } from "@/lib/types";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const d = await api<StoryDetail>(`/stories/${(await params).id}`);
  return { title: d.story.title };
}

export default async function StoryPage({ params }: Props) {
  const d = await api<StoryDetail>(`/stories/${(await params).id}`);
  const [digestBody, missing] = (d.digest ?? "").split(/(?=尚未披露：)/);
  return (
    <>
      <PageHeader
        title={d.story.title}
        desc={`${d.story.item_count} 条报道 · ${d.story.source_count} 家信源 · 首报 ${formatDateTime(d.first_seen_at)} · 最近 ${formatDateTime(d.last_seen_at)}`}
      />
      {d.digest ? (
        <Card className="mb-6 p-4">
          <h2 className="mb-1.5 text-sm font-semibold text-ink">AI 综述</h2>
          <p className="leading-relaxed text-ink-2">{digestBody}</p>
          {missing ? <p className="mt-2 rounded-md bg-lead-soft px-3 py-2 text-sm text-lead">{missing}</p> : null}
        </Card>
      ) : null}
      <h2 className="mb-1 text-sm font-semibold text-ink">报道时间线</h2>
      <ol className="relative border-l border-line pl-5">
        {d.timeline.map((item) => (
          <li key={item.id} className="relative">
            <span className="absolute top-6 -left-[25px] size-2.5 rounded-full border-2 border-bg bg-accent" aria-hidden />
            <ItemCardView item={item} showDate inStory />
          </li>
        ))}
      </ol>
    </>
  );
}
