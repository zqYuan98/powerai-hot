"use client";

import { useEffect, useState } from "react";

import { Button, Empty } from "@/components/ui";
import { send } from "@/lib/api.client";
import { clearLocalStars, useLocalStars } from "@/lib/local";
import type { ItemCard } from "@/lib/types";

import { ItemCardView } from "./ItemCard";

/** 访客的收藏：id 存在本机，内容每次从服务器取最新的（已下线的条目自动跳过）。 */
export function LocalStarred() {
  const ids = useLocalStars();
  const key = ids.join(",");
  const [loaded, setLoaded] = useState<{ key: string; items: ItemCard[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    const params = new URLSearchParams(key.split(",").slice(0, 100).map((id) => ["ids", id]));
    send<ItemCard[]>(`/items/by-ids?${params}`)
      .then((items) => !cancelled && setLoaded({ key, items }))
      .catch((e: unknown) => !cancelled && setError(e instanceof Error ? e.message : "加载失败"));
    return () => {
      cancelled = true;
    };
  }, [key]);

  if (!key) return <Empty title="还没有收藏">点击任意条目右上角的星标即可收藏。</Empty>;
  if (error) return <Empty title="收藏加载失败">{error}</Empty>;
  // 取消收藏后先按本机列表过滤，不必等重新请求
  const items = loaded?.items.filter((i) => ids.includes(i.id));
  if (!items) return <p className="py-10 text-center text-sm text-muted">加载中…</p>;

  return (
    <div>
      <div className="divide-y divide-line">
        {items.map((item) => (
          <ItemCardView key={item.id} item={item} showDate />
        ))}
      </div>
      <div className="py-6 text-center">
        <Button
          variant="ghost"
          onClick={() => {
            if (confirm("清空这台设备上的全部收藏？")) clearLocalStars();
          }}
        >
          清空收藏
        </Button>
      </div>
    </div>
  );
}
