import { ChannelTabs } from "@/components/feed/ChannelTabs";
import { FeedList } from "@/components/feed/FeedList";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api.server";
import { relativeTime } from "@/lib/format";
import type { ItemCard, Meta, Page } from "@/lib/types";
import { isAdmin } from "@/lib/viewer";

export default async function SelectedPage({ searchParams }: { searchParams: Promise<{ channel?: string }> }) {
  const { channel = "" } = await searchParams;
  const query = { view: "selected", ...(channel ? { channel } : {}) };
  const [page, meta, admin] = await Promise.all([
    api<Page<ItemCard>>("/items", { ...query, limit: 30 }),
    api<Meta>("/meta"),
    isAdmin(),
  ]);

  return (
    <>
      <PageHeader
        title="精选"
        desc={
          meta.last_collect_at
            ? `AI 按电力基建相关度、商机价值、确定性等维度打分筛出 · 最近采集 ${relativeTime(meta.last_collect_at)}`
            : "AI 按电力基建相关度、商机价值、确定性等维度打分筛出"
        }
      />
      {admin && !meta.llm_enabled ? (
        <p className="mb-4 rounded-md bg-lead-soft px-3 py-2 text-sm text-lead">
          尚未配置 LLM_API_KEY：新采集的条目会停在「待处理」，不会进入精选。
        </p>
      ) : null}
      <ChannelTabs base="/" active={channel} meta={meta} />
      <FeedList
        key={channel}
        initial={page}
        query={query}
        emptyTitle="还没有精选情报"
        emptyHint="采集并完成 AI 精读后，这里会按天出现。"
      />
    </>
  );
}
