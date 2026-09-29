"use client";

import { ExternalLink, Undo2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge, Button, Card, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";
import { cn } from "@/lib/cn";
import { formatDate, TIER_LABEL } from "@/lib/format";
import type { GoldCase, GoldStats } from "@/lib/types";

type Decision = GoldCase["decision"] & string;

export const DECISIONS: {
  value: Decision;
  label: string;
  key: string;
  tone: string;
}[] = [
  { value: "select", label: "该选", key: "1", tone: "bg-ok-soft text-ok" },
  {
    value: "reject",
    label: "不该选",
    key: "2",
    tone: "bg-danger-soft text-danger",
  },
  { value: "either", label: "两可", key: "3", tone: "bg-surface-2 text-ink-2" },
];
const BY_VALUE = Object.fromEntries(DECISIONS.map((d) => [d.value, d])) as Record<Decision, (typeof DECISIONS)[number]>;

export function GoldLabeler({ initialCase, initialStats }: { initialCase: GoldCase | null; initialStats: GoldStats }) {
  const [item, setItem] = useState<GoldCase | null>(initialCase);
  const [stats, setStats] = useState(initialStats);
  const [note, setNote] = useState(initialCase?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skippedAny, setSkippedAny] = useState(false);
  const skipped = useRef<number[]>([]);

  const show = useCallback((next: GoldCase | null) => {
    setItem(next);
    setNote(next?.note ?? "");
  }, []);

  const loadNext = useCallback(async () => {
    const q = skipped.current.map((id) => `skip=${id}`).join("&");
    show(await send<GoldCase | null>(`/gold/next${q ? `?${q}` : ""}`));
  }, [show]);

  const run = useCallback(
    async (fn: () => Promise<void>) => {
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        await fn();
      } catch (e) {
        setError(e instanceof Error ? e.message : "操作失败");
      } finally {
        setBusy(false);
      }
    },
    [busy],
  );

  const label = useCallback(
    (decision: Decision) =>
      run(async () => {
        if (!item) return;
        setStats(
          await send<GoldStats>(`/gold/${item.item_id}`, {
            method: "PUT",
            body: { decision, note },
          }),
        );
        await loadNext();
      }),
    [run, item, note, loadNext],
  );

  const skip = useCallback(
    () =>
      run(async () => {
        if (!item) return;
        skipped.current.push(item.item_id);
        setSkippedAny(true);
        await loadNext();
      }),
    [run, item, loadNext],
  );

  const relabel = (itemId: number) =>
    run(async () => {
      show(await send<GoldCase>(`/gold/${itemId}`));
    });

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement;
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || e.metaKey || e.ctrlKey || e.altKey) return;
      const hit = DECISIONS.find((d) => d.key === e.key);
      if (hit) void label(hit.value);
      else if (e.key === "s" || e.key === "S") void skip();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [label, skip]);

  const pct = Math.min(100, Math.round((stats.total / stats.target) * 100));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2">
        <span className="font-medium text-ink">
          已标 {stats.total} / 建议 {stats.target}
        </span>
        {DECISIONS.map((d) => (
          <span key={d.value}>
            {d.label} {stats.decision[d.value] ?? 0}
          </span>
        ))}
        <span className="text-muted">
          开发集 {stats.split.development ?? 0} · 留出集 {stats.split.holdout ?? 0}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <div className="h-full bg-accent transition-all" style={{ width: `${pct}%` }} />
      </div>

      {item ? (
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="text-ink-2">{item.source_name}</span>
            <Badge className="bg-surface-2 text-ink-2">{TIER_LABEL[item.tier] ?? item.tier}</Badge>
            <span>发布 {item.published_at ? formatDate(item.published_at) : "未知"}</span>
            <span>发现 {formatDate(item.first_seen_at)}</span>
            {item.decision ? (
              <Badge className={BY_VALUE[item.decision].tone}>原标注：{BY_VALUE[item.decision].label}</Badge>
            ) : null}
          </div>
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="group flex items-start gap-1.5 text-base leading-snug font-semibold text-ink hover:text-accent"
          >
            <span>{item.title}</span>
            <ExternalLink className="mt-1 size-3.5 shrink-0 text-muted group-hover:text-accent" />
          </a>
          {item.body ? (
            <div className="max-h-72 overflow-y-auto rounded-md bg-surface-2 p-3 text-sm leading-relaxed whitespace-pre-line text-ink-2">
              {item.body}
            </div>
          ) : (
            <p className="text-sm text-muted">没有抓到正文，只凭标题判断；拿不准可以点标题看原文。</p>
          )}
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="备注（可选）：为什么该选/不该选，以后改评分标准时用得上"
            aria-label="备注"
            maxLength={500}
            className={inputClass}
          />
          <div className="flex flex-wrap gap-2">
            {DECISIONS.map((d) => (
              <Button
                key={d.value}
                disabled={busy}
                onClick={() => void label(d.value)}
                className={cn("min-w-24", d.tone)}
              >
                {d.label}
                <kbd className="font-sans text-xs opacity-60">{d.key}</kbd>
              </Button>
            ))}
            <Button variant="ghost" disabled={busy} onClick={() => void skip()}>
              跳过 <kbd className="font-sans text-xs opacity-60">S</kbd>
            </Button>
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
        </Card>
      ) : (
        <Card className="p-6 text-center text-sm text-ink-2">
          {skippedAny ? "剩下的都跳过了，刷新页面可以再看被跳过的。" : "没有待标注的条目了。"}
        </Card>
      )}

      {stats.recent.length ? (
        <div className="space-y-1">
          <h3 className="text-xs font-medium text-muted">最近标注</h3>
          <ul className="divide-y divide-line rounded-lg border border-line bg-surface text-sm">
            {stats.recent.map((r) => (
              <li key={r.item_id} className="flex items-center gap-2 px-3 py-1.5">
                <Badge className={BY_VALUE[r.decision].tone}>{BY_VALUE[r.decision].label}</Badge>
                <span className="min-w-0 flex-1 truncate text-ink-2">{r.title}</span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void relabel(r.item_id)}
                  className="inline-flex shrink-0 items-center gap-1 text-xs text-muted hover:text-ink"
                >
                  <Undo2 className="size-3" /> 改标
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
