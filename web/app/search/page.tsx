import type { Metadata } from "next";

import { ItemCardView } from "@/components/feed/ItemCard";
import { Empty, PageHeader } from "@/components/ui";
import { api } from "@/lib/api.server";
import type { ItemCard } from "@/lib/types";

export const metadata: Metadata = { title: "搜索" };

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const q = ((await searchParams).q ?? "").trim();
  if (!q) {
    return (
      <>
        <PageHeader title="搜索" />
        <Empty title="输入关键词开始搜索">支持项目名、业主、地区、设备等；配置 Embedding 后还会做语义检索。</Empty>
      </>
    );
  }
  const results = await api<ItemCard[]>("/items/search", { q, limit: 50 });
  return (
    <>
      <PageHeader title={`搜索：${q}`} desc={`${results.length} 条结果（关键词命中优先，其后为语义相近）`} />
      {results.length ? (
        <div className="divide-y divide-line">
          {results.map((item) => (
            <ItemCardView key={item.id} item={item} showDate />
          ))}
        </div>
      ) : (
        <Empty title="没有找到相关情报">换个说法试试，比如用项目所在地或设备名称。</Empty>
      )}
    </>
  );
}
