"use client";

import { Star } from "lucide-react";
import { useState } from "react";

import { useIsAdmin } from "@/components/layout/ViewerProvider";
import { send } from "@/lib/api.client";
import { cn } from "@/lib/cn";
import { toggleLocalStar, useLocalStars } from "@/lib/local";

/** 管理员的收藏存服务器；访客的收藏存本机浏览器。 */
export function StarButton({ id, starred }: { id: number; starred: boolean }) {
  return useIsAdmin() ? <ServerStar id={id} starred={starred} /> : <LocalStar id={id} />;
}

function ServerStar({ id, starred }: { id: number; starred: boolean }) {
  const [on, setOn] = useState(starred);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    const next = !on;
    setOn(next); // 乐观更新，失败回滚
    setBusy(true);
    try {
      await send(`/items/${id}`, { method: "PATCH", body: { starred: next } });
    } catch {
      setOn(!next);
    } finally {
      setBusy(false);
    }
  }

  return <StarIcon on={on} disabled={busy} onClick={toggle} />;
}

function LocalStar({ id }: { id: number }) {
  const on = useLocalStars().includes(id);
  return <StarIcon on={on} onClick={() => toggleLocalStar(id)} />;
}

function StarIcon({ on, disabled, onClick }: { on: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={on}
      aria-label={on ? "取消收藏" : "收藏"}
      className="relative z-10 -m-1.5 flex size-8 items-center justify-center rounded-md text-muted hover:text-lead"
    >
      <Star className={cn("size-4", on && "fill-lead text-lead")} aria-hidden />
    </button>
  );
}
