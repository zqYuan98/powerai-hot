"use client";

import { Star } from "lucide-react";
import { useState } from "react";

import { send } from "@/lib/api.client";
import { cn } from "@/lib/cn";

export function StarButton({ id, starred }: { id: number; starred: boolean }) {
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

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={on}
      aria-label={on ? "取消收藏" : "收藏"}
      className="relative z-10 -m-1.5 flex size-8 items-center justify-center rounded-md text-muted hover:text-lead"
    >
      <Star className={cn("size-4", on && "fill-lead text-lead")} aria-hidden />
    </button>
  );
}
