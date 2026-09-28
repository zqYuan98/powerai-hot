import type { Metadata } from "next";

import { Empty, TabLinks } from "@/components/ui";
import { api } from "@/lib/api.server";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import type { JobOut } from "@/lib/types";

export const metadata: Metadata = { title: "任务队列" };

const KIND_LABEL: Record<string, string> = {
  collect: "采集",
  process: "处理",
  schedule_collect: "调度采集",
  retry_failed: "重试失败",
  heat: "热度",
  story_digests: "事件综述",
  digest: "日报/周报",
  deadline_reminders: "截止提醒",
  maintenance: "维护",
  backup: "备份",
};
const STATUS_TONE: Record<string, string> = {
  queued: "text-muted",
  running: "text-accent",
  done: "text-ok",
  failed: "text-danger",
};

function summary(job: JobOut): string {
  const r = (job.result ?? {}) as Record<string, unknown>;
  const n = (k: string) => Number(r[k] ?? 0);
  if (job.kind === "collect") return `${String(r.source_key ?? "")} 抓 ${n("fetched")} 新 ${n("new_ids")}`;
  if (job.kind === "process")
    return `精读 ${n("analyzed")} 精选 ${n("selected")} 淘汰 ${n("screened_out")} 失败 ${n("failed")}`;
  if (job.kind === "schedule_collect") return `派发 ${Array.isArray(r.enqueued) ? r.enqueued.length : 0} 个信源`;
  return Object.keys(r).length ? JSON.stringify(r).slice(0, 80) : "";
}

export default async function JobsPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const status = (await searchParams).status ?? "";
  const jobs = await api<JobOut[]>("/jobs", { status, limit: 100 });
  return (
    <>
      <TabLinks
        active={status}
        tabs={[
          { key: "", href: "/settings/jobs", label: "全部" },
          { key: "queued", href: "/settings/jobs?status=queued", label: "排队" },
          { key: "running", href: "/settings/jobs?status=running", label: "执行中" },
          { key: "failed", href: "/settings/jobs?status=failed", label: "失败" },
        ]}
      />
      {jobs.length === 0 ? (
        <Empty title="没有任务" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">类型</th>
                <th className="px-3 py-2 font-medium">状态</th>
                <th className="px-3 py-2 font-medium">创建</th>
                <th className="px-3 py-2 font-medium">结果</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {jobs.map((j) => (
                <tr key={j.id} className="align-top">
                  <td className="px-3 py-1.5 text-muted tabular-nums">{j.id}</td>
                  <td className="px-3 py-1.5 whitespace-nowrap text-ink">{KIND_LABEL[j.kind] ?? j.kind}</td>
                  <td className={cn("px-3 py-1.5 whitespace-nowrap", STATUS_TONE[j.status])}>
                    {j.status}
                    {j.attempts > 1 ? ` ×${j.attempts}` : ""}
                  </td>
                  <td className="px-3 py-1.5 whitespace-nowrap text-ink-2">{formatDateTime(j.created_at)}</td>
                  <td className="px-3 py-1.5 text-xs text-ink-2">
                    {j.error ? <span className="text-danger">{j.error.slice(0, 200)}</span> : summary(j)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
