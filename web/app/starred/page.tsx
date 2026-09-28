import type { Metadata } from "next";

import { FeedList } from "@/components/feed/FeedList";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api.server";
import type { ItemCard, Page } from "@/lib/types";

export const metadata: Metadata = { title: "收藏" };

export default async function StarredPage() {
  const page = await api<Page<ItemCard>>("/items", { view: "starred", limit: 30 });
  return (
    <>
      <PageHeader title="收藏" desc="点击任意条目右上角的星标即可收藏；详情页可以写笔记。" />
      <FeedList initial={page} query={{ view: "starred" }} emptyTitle="还没有收藏" />
    </>
  );
}
