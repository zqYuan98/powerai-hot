"use client";

import { useState } from "react";

import { send } from "@/lib/api.client";
import { cn } from "@/lib/cn";
import { FOLLOW_LABEL } from "@/lib/format";
import type { FollowStatus, LeadOut } from "@/lib/types";

const ORDER: FollowStatus[] = ["new", "watching", "following", "closed", "ignored"];
const TONE: Record<FollowStatus, string> = {
  new: "text-muted",
  watching: "text-accent",
  following: "text-lead font-medium",
  closed: "text-ok",
  ignored: "text-muted line-through",
};

/** 商机跟进状态下拉，改动立即保存。 */
export function FollowControl({ itemId, status, compact = false }: { itemId: number; status: FollowStatus; compact?: boolean }) {
  const [value, setValue] = useState(status);
  const [error, setError] = useState(false);

  async function change(next: FollowStatus) {
    const prev = value;
    setValue(next);
    setError(false);
    try {
      await send<LeadOut>(`/leads/${itemId}`, { method: "PATCH", body: { follow_status: next } });
    } catch {
      setValue(prev);
      setError(true);
    }
  }

  return (
    <select
      value={value}
      onChange={(e) => change(e.target.value as FollowStatus)}
      aria-label="跟进状态"
      className={cn(
        "relative z-10 rounded-md border border-line bg-surface text-sm focus:border-accent focus:outline-none",
        compact ? "h-8 px-1.5" : "h-9 px-2.5",
        TONE[value],
        error && "border-danger",
      )}
    >
      {ORDER.map((s) => (
        <option key={s} value={s}>
          {FOLLOW_LABEL[s]}
        </option>
      ))}
    </select>
  );
}
