"use client";

import { ChevronDown, ChevronRight, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useState } from "react";

import { Badge, Button } from "@/components/ui";
import { send } from "@/lib/api.client";
import { cn } from "@/lib/cn";
import { CHANNEL_LABEL, formatDateTime, relativeTime, TIER_LABEL } from "@/lib/format";
import type { Channel, Ok, SourceOut, SourceRunOut } from "@/lib/types";

function health(s: SourceOut): { label: string; tone: string } {
  if (!s.enabled) return { label: "已停用", tone: "bg-surface-2 text-muted" };
  if (!s.last_run_at) return { label: "未运行", tone: "bg-surface-2 text-muted" };
  if (s.fail_streak > 0) return { label: `连续失败 ${s.fail_streak}`, tone: "bg-danger-soft text-danger" };
  if (s.last_error) return { label: "部分失败", tone: "bg-lead-soft text-lead" };
  return { label: "正常", tone: "bg-ok-soft text-ok" };
}

function Runs({ sourceId }: { sourceId: number }) {
  const [runs, setRuns] = useState<SourceRunOut[] | null>(null);
  useEffect(() => {
    let alive = true;
    send<SourceRunOut[]>(`/sources/${sourceId}/runs?limit=15`).then(
      (r) => alive && setRuns(r),
      () => alive && setRuns([]),
    );
    return () => {
      alive = false;
    };
  }, [sourceId]);
  if (runs === null) return <p className="py-2 text-xs text-muted">加载中…</p>;
  if (runs.length === 0) return <p className="py-2 text-xs text-muted">暂无运行记录</p>;
  return (
    <table className="w-full text-xs">
      <tbody>
        {runs.map((r) => (
          <tr key={r.id} className="border-t border-line">
            <td className="py-1 pr-3 whitespace-nowrap text-muted">{formatDateTime(r.started_at)}</td>
            <td className={cn("py-1 pr-3", r.transport_status === "ok" ? "text-ok" : r.transport_status === "partial" ? "text-lead" : "text-danger")}>
              {r.transport_status}
              {r.http_status ? ` ${r.http_status}` : ""}
            </td>
            <td className="py-1 pr-3 whitespace-nowrap text-ink-2">
              抓 {r.fetched} / 新 {r.new_count}
            </td>
            <td className="py-1 pr-3 text-muted">{(r.duration_ms / 1000).toFixed(1)}s</td>
            <td className="py-1 text-danger">{r.error}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SourcesTable({ sources: initial }: { sources: SourceOut[] }) {
  const [sources, setSources] = useState(initial);
  const [open, setOpen] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function patch(id: number, body: Partial<Pick<SourceOut, "enabled" | "interval_min">>) {
    try {
      const updated = await send<SourceOut>(`/sources/${id}`, { method: "PATCH", body });
      setSources((prev) => prev.map((s) => (s.id === id ? { ...s, ...updated } : s)));
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "保存失败");
    }
  }

  async function collect(s: SourceOut) {
    try {
      const r = await send<Ok>(`/sources/${s.id}/collect`, { method: "POST" });
      setNotice(`${s.name}：${r.detail ?? "已加入队列"}`);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "操作失败");
    }
  }

  return (
    <div>
      {notice ? <p className="mb-2 rounded-md bg-accent-soft px-3 py-1.5 text-sm text-accent">{notice}</p> : null}
      <div className="overflow-x-auto rounded-lg border border-line bg-surface">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="border-b border-line text-left text-xs text-muted">
            <tr>
              <th className="w-6" />
              <th className="px-2 py-2 font-medium">信源</th>
              <th className="px-2 py-2 font-medium">状态</th>
              <th className="px-2 py-2 font-medium">最近成功</th>
              <th className="px-2 py-2 text-right font-medium">24h 成功</th>
              <th className="px-2 py-2 text-right font-medium">7 天新增 / 精选</th>
              <th className="px-2 py-2 font-medium">间隔</th>
              <th className="px-2 py-2 font-medium">启用</th>
              <th className="px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => {
              const h = health(s);
              const expanded = open === s.id;
              return (
                <Fragment key={s.id}>
                  <tr className="border-t border-line align-top">
                    <td className="py-2 pl-2">
                      <button
                        type="button"
                        onClick={() => setOpen(expanded ? null : s.id)}
                        aria-label={expanded ? "收起运行记录" : "展开运行记录"}
                        aria-expanded={expanded}
                        className="text-muted hover:text-ink"
                      >
                        {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                      </button>
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium text-ink">{s.name}</span>
                        <Badge className="tone-muted">{TIER_LABEL[s.tier] ?? s.tier}</Badge>
                        <Badge className="tone-muted">{CHANNEL_LABEL[s.category as Channel] ?? s.category}</Badge>
                      </div>
                      <div className="mt-0.5 text-xs text-muted">
                        {s.key} · {s.kind}
                      </div>
                      {s.notes ? <div className="mt-0.5 max-w-md text-xs text-muted">{s.notes}</div> : null}
                      {s.last_error ? <div className="mt-0.5 max-w-md text-xs text-danger">{s.last_error}</div> : null}
                    </td>
                    <td className="px-2 py-2">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs whitespace-nowrap", h.tone)}>{h.label}</span>
                    </td>
                    <td className="px-2 py-2 text-xs whitespace-nowrap text-ink-2">
                      {s.last_ok_at ? relativeTime(s.last_ok_at) : "—"}
                    </td>
                    <td className="px-2 py-2 text-right text-xs text-ink-2 tabular-nums">
                      {s.ok_24h}/{s.runs_24h}
                    </td>
                    <td className="px-2 py-2 text-right text-xs text-ink-2 tabular-nums">
                      {s.new_7d} / <span className="text-accent">{s.selected_7d}</span>
                    </td>
                    <td className="px-2 py-2">
                      <select
                        value={s.interval_min}
                        onChange={(e) => patch(s.id, { interval_min: Number(e.target.value) })}
                        aria-label={`${s.name} 采集间隔`}
                        className="h-8 rounded-md border border-line bg-surface px-1.5 text-xs"
                      >
                        {[...new Set([30, 60, 120, 240, 360, 720, 1440, s.interval_min])]
                          .sort((a, b) => a - b)
                          .map((m) => (
                            <option key={m} value={m}>
                              {m < 60 ? `${m} 分钟` : `${m / 60} 小时`}
                            </option>
                          ))}
                      </select>
                    </td>
                    <td className="px-2 py-2">
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        onChange={(e) => patch(s.id, { enabled: e.target.checked })}
                        aria-label={`启用 ${s.name}`}
                        className="size-4 accent-accent"
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Button variant="ghost" className="h-8 px-2" onClick={() => collect(s)} title="立即采集">
                        <Play className="size-3.5" aria-hidden /> 采集
                      </Button>
                    </td>
                  </tr>
                  {expanded ? (
                    <tr>
                      <td />
                      <td colSpan={8} className="px-2 pb-3">
                        <Runs sourceId={s.id} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RetryFailedButton({ count }: { count: number }) {
  const router = useRouter();
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="flex items-center gap-3">
      <Button
        onClick={async () => {
          try {
            const r = await send<Ok>("/items/retry-failed", { method: "POST" });
            setMsg(r.detail ?? "已重新排队");
            router.refresh();
          } catch (e) {
            setMsg(e instanceof Error ? e.message : "操作失败");
          }
        }}
      >
        重试 {count} 条失败条目
      </Button>
      <span className="text-xs text-muted">{msg ?? "修复模型配置（Key、模型名、额度）后使用"}</span>
    </div>
  );
}
