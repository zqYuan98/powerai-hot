"use client";

import { useState } from "react";

import { Button, Empty } from "@/components/ui";
import { send } from "@/lib/api.client";
import { dayLabel, groupByDay } from "@/lib/format";
import type { ItemCard, Page } from "@/lib/types";

import { ItemCardView } from "./ItemCard";

/** 按天分组的信息流，游标分页「加载更多」。query 为除 cursor 外的查询参数。 */
export function FeedList({
  initial,
  query,
  emptyTitle = "暂无内容",
  emptyHint,
}: {
  initial: Page<ItemCard>;
  query: Record<string, string>;
  emptyTitle?: string;
  emptyHint?: string;
}) {
  const [items, setItems] = useState(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function more() {
    if (!cursor) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ ...query, cursor });
      const page = await send<Page<ItemCard>>(`/items?${params}`);
      setItems((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0) return <Empty title={emptyTitle}>{emptyHint}</Empty>;

  return (
    <div>
      {groupByDay(items).map((group) => (
        <section key={group.key} aria-labelledby={`day-${group.key}`} className="mb-2">
          <h2
            id={`day-${group.key}`}
            className="sticky top-14 z-10 -mx-4 flex items-baseline gap-2 bg-bg/95 px-4 py-2 text-sm font-semibold text-ink backdrop-blur"
          >
            {dayLabel(group.key)}
            <span className="text-xs font-normal text-muted">{group.items.length} 条</span>
          </h2>
          <div className="divide-y divide-line">
            {group.items.map((item) => (
              <ItemCardView key={item.id} item={item} />
            ))}
          </div>
        </section>
      ))}
      <div className="py-6 text-center">
        {error ? <p className="mb-2 text-sm text-danger">{error}</p> : null}
        {cursor ? (
          <Button onClick={more} disabled={loading}>
            {loading ? "加载中…" : "加载更多"}
          </Button>
        ) : (
          <p className="text-xs text-muted">没有更多了</p>
        )}
      </div>
    </div>
  );
}
