import type { Metadata } from "next";

import { RetryFailedButton, SourcesTable } from "@/components/settings/SourcesTable";
import { Card } from "@/components/ui";
import { api } from "@/lib/api.server";
import type { Meta, PipelineStats, SourceOut } from "@/lib/types";

export const metadata: Metadata = { title: "信源与流水线" };

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <Card className="p-3">
      <div className={`font-mono text-2xl font-semibold tabular-nums ${tone ?? "text-ink"}`}>{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </Card>
  );
}

export default async function SettingsPage() {
  const [stats, sources, meta] = await Promise.all([
    api<PipelineStats>("/pipeline"),
    api<SourceOut[]>("/sources"),
    api<Meta>("/meta"),
  ]);
  const flags = [
    { ok: meta.llm_enabled, label: "LLM 分析", hint: "LLM_API_KEY" },
    { ok: meta.embedding_enabled, label: "向量归并/语义搜索", hint: "EMBEDDING_API_KEY" },
    { ok: meta.push_enabled, label: "飞书推送", hint: "FEISHU_WEBHOOK_URL" },
  ];

  return (
    <div className="space-y-6">
      <section>
        <div className="mb-2 flex flex-wrap gap-2">
          {flags.map((f) => (
            <span
              key={f.label}
              className={`rounded-full px-2.5 py-0.5 text-xs ${f.ok ? "bg-ok-soft text-ok" : "bg-surface-2 text-muted"}`}
              title={f.ok ? "已启用" : `未配置 ${f.hint}`}
            >
              {f.ok ? "●" : "○"} {f.label}
            </span>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          <Stat label="24h 新增" value={stats.items_24h} />
          <Stat label="24h 精读" value={stats.analyzed_24h} />
          <Stat label="24h 精选" value={stats.selected_24h} tone="text-accent" />
          <Stat label="24h 淘汰" value={stats.screened_out_24h} />
          <Stat label="失败待处理" value={stats.failed_pending} tone={stats.failed_pending ? "text-danger" : undefined} />
          <Stat label="排队任务" value={stats.queued_jobs} />
          <Stat label="执行中" value={stats.running_jobs} />
        </div>
        {stats.failed_pending ? (
          <div className="mt-3">
            <RetryFailedButton count={stats.failed_pending} />
          </div>
        ) : null}
      </section>
      <section>
        <h2 className="mb-2 text-base font-semibold text-ink">信源</h2>
        <SourcesTable sources={sources} />
      </section>
    </div>
  );
}
