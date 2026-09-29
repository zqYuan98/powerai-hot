import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Card, Empty } from "@/components/ui";
import { api } from "@/lib/api.server";
import { cn } from "@/lib/cn";
import {
  CHANNEL_LABEL,
  EVAL_MODE_LABEL,
  EVAL_SPLIT_LABEL,
  formatDateTime,
  formatRatio,
  TIER_LABEL,
} from "@/lib/format";
import type { Channel, EvalRunDetail } from "@/lib/types";

export const metadata: Metadata = { title: "评测详情" };

type Confusion = {
  n: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  predicted: number;
} & Record<"precision" | "recall" | "f1" | "accuracy", number | null>;
type Case = {
  item_id: number;
  gold: string;
  stratum: string;
  note: string | null;
  title: string;
  title_zh: string | null;
  source: string;
  tier: string;
  channel: string;
  stage: string;
  score: number | null;
  selected: boolean;
  reason: string | null;
  dims: Record<string, number | null> | null;
};

const STRATUM_LABEL: Record<string, string> = {
  selected: "当时入选",
  near: "差一点入选",
  low: "低分",
  screened: "被淘汰",
  other: "其他",
};
const STAGE_LABEL: Record<string, string> = {
  rule: "规则拦截",
  screen: "初筛淘汰",
  analyzed: "精读",
  failed: "模型失败",
  unjudged: "未判断",
};
const DIM_LABEL: Record<string, string> = {
  relevance: "相关",
  opportunity: "商机",
  certainty: "确定",
  timeliness: "时效",
  impact: "影响",
};

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-3">
      <div className="font-mono text-2xl font-semibold text-ink tabular-nums">{value}</div>
      <div className="text-xs text-muted">
        {label}
        {sub ? <span className="ml-1">{sub}</span> : null}
      </div>
    </Card>
  );
}

function Breakdown({
  title,
  rows,
  label,
}: {
  title: string;
  rows: Record<string, Confusion>;
  label: (k: string) => string;
}) {
  const entries = Object.entries(rows).filter(([, v]) => v.n > 0);
  if (!entries.length) return null;
  return (
    <div>
      <h3 className="mb-1 text-xs font-medium text-muted">{title}</h3>
      <ul className="space-y-0.5 text-sm tabular-nums">
        {entries.map(([k, v]) => (
          <li key={k} className="flex justify-between gap-3">
            <span className="text-ink-2">{label(k)}</span>
            <span className={v.fp + v.fn ? "text-danger" : "text-muted"}>
              判错 {v.fp + v.fn}/{v.n}
              {v.fp ? ` · 多选 ${v.fp}` : ""}
              {v.fn ? ` · 漏选 ${v.fn}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function EvalRunPage({ params }: { params: Promise<{ id: string }> }) {
  const run = await api<EvalRunDetail>(`/eval-runs/${(await params).id}`);
  const m = run.metrics as Confusion & {
    total: number;
    either: number;
    excluded: number;
    by_stratum: Record<string, Confusion>;
    by_tier: Record<string, Confusion>;
    by_channel: Record<string, Confusion>;
  };
  const sweep = run.sweep as ({ threshold: number } & Confusion)[];
  const errors = run.errors as Case[];
  const p = run.params as {
    thresholds?: Record<string, number>;
    tier_coef?: Record<string, number>;
    screen_model?: string;
    analyze_model?: string;
    config_hash?: string;
  };
  const bestF1 = Math.max(...sweep.map((s) => s.f1 ?? 0));

  return (
    <div className="space-y-5">
      <div>
        <Link href="/settings/gold" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
          <ArrowLeft className="size-3.5" /> 精选校准
        </Link>
        <h2 className="mt-1 text-base font-semibold text-ink">
          #{run.id} {run.label}
        </h2>
        <p className="text-sm text-muted">
          {EVAL_MODE_LABEL[run.mode] ?? run.mode} · {EVAL_SPLIT_LABEL[run.split] ?? run.split} ·{" "}
          {formatDateTime(run.created_at)}
          {run.cost_yuan ? ` · 花费 ¥${run.cost_yuan.toFixed(3)}` : ""}
          {p.config_hash ? ` · 配置 ${p.config_hash}` : ""}
          {p.analyze_model ? ` · 精读 ${p.analyze_model}` : ""}
        </p>
      </div>

      {run.status !== "done" ? (
        <Empty title={run.status === "failed" ? "评测失败" : "评测进行中"}>{run.error ?? "完成后刷新本页"}</Empty>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="查准" sub="选出的有多少是对的" value={formatRatio(m.precision)} />
            <Stat label="查全" sub="该选的选上了多少" value={formatRatio(m.recall)} />
            <Stat label="F1" value={m.f1 === null ? "–" : String(m.f1)} />
            <Stat label="准确率" value={formatRatio(m.accuracy)} />
          </div>
          <p className="text-sm text-ink-2">
            共 {m.total} 条，计入 {m.n} 条（两可 {m.either}，没判出结果 {m.excluded}）。选出 {m.predicted} 条，其中对的{" "}
            {m.tp} 条；该选的 {m.tp + m.fn} 条。
            {p.thresholds
              ? ` 当时门槛 ${Object.entries(p.thresholds)
                  .map(([t, v]) => `${TIER_LABEL[t] ?? t} ${v}`)
                  .join(" / ")}，档位系数 ${Object.entries(p.tier_coef ?? {})
                  .map(([t, v]) => `${TIER_LABEL[t] ?? t} ×${v}`)
                  .join(" / ")}。`
              : ""}
          </p>

          <Card className="grid gap-4 p-4 sm:grid-cols-3">
            <Breakdown title="按抽样层" rows={m.by_stratum} label={(k) => STRATUM_LABEL[k] ?? k} />
            <Breakdown title="按信源档位" rows={m.by_tier} label={(k) => TIER_LABEL[k] ?? k} />
            <Breakdown title="按频道" rows={m.by_channel} label={(k) => CHANNEL_LABEL[k as Channel] ?? k} />
          </Card>

          <section>
            <h3 className="mb-1 text-sm font-semibold text-ink">判错 {errors.length} 条</h3>
            <p className="mb-2 text-xs text-muted">
              多选：不该选却进了精选，多半是噪声没压住；漏选：该选没选上，多半是评分标准没说清它为什么重要。
            </p>
            {errors.length === 0 ? (
              <Empty title="没有判错的条目" />
            ) : (
              <ul className="space-y-2">
                {errors.map((c) => (
                  <li key={c.item_id}>
                    <Card className="space-y-1 p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <Badge className={c.selected ? "bg-danger-soft text-danger" : "bg-lead-soft text-lead"}>
                          {c.selected ? "多选" : "漏选"}
                        </Badge>
                        <span className="font-mono text-ink tabular-nums">
                          {c.score !== null ? c.score.toFixed(0) : STAGE_LABEL[c.stage]}
                        </span>
                        <span className="text-ink-2">{c.source}</span>
                        <span className="text-muted">
                          {TIER_LABEL[c.tier] ?? c.tier} · {CHANNEL_LABEL[c.channel as Channel] ?? c.channel} ·{" "}
                          {STRATUM_LABEL[c.stratum] ?? c.stratum}
                        </span>
                      </div>
                      <Link href={`/items/${c.item_id}`} className="block font-medium text-ink hover:text-accent">
                        {c.title_zh || c.title}
                      </Link>
                      {c.dims ? (
                        <p className="text-xs text-muted tabular-nums">
                          {Object.entries(c.dims)
                            .map(([k, v]) => `${DIM_LABEL[k] ?? k} ${v ?? "–"}`)
                            .join(" · ")}
                        </p>
                      ) : null}
                      {c.reason ? <p className="text-xs text-ink-2">系统：{c.reason}</p> : null}
                      {c.note ? <p className="text-xs text-ink-2">你的备注：{c.note}</p> : null}
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="mb-1 text-sm font-semibold text-ink">门槛扫描</h3>
            <p className="mb-2 text-xs text-muted">
              所有档位用同一个门槛，作用在含档位系数的总分上；被规则/初筛淘汰和已过截止的始终不选。F1 最高的行已标出。
            </p>
            <div className="overflow-x-auto rounded-lg border border-line bg-surface">
              <table className="w-full min-w-[420px] text-sm tabular-nums">
                <thead className="border-b border-line text-right text-xs text-muted">
                  <tr>
                    <th className="px-3 py-1.5 font-medium">门槛</th>
                    <th className="px-3 py-1.5 font-medium">选出</th>
                    <th className="px-3 py-1.5 font-medium">查准</th>
                    <th className="px-3 py-1.5 font-medium">查全</th>
                    <th className="px-3 py-1.5 font-medium">F1</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line text-right">
                  {sweep.map((s) => (
                    <tr key={s.threshold} className={cn(bestF1 > 0 && s.f1 === bestF1 && "bg-accent-soft")}>
                      <td className="px-3 py-1 text-ink">{s.threshold}</td>
                      <td className="px-3 py-1 text-ink-2">{s.predicted}</td>
                      <td className="px-3 py-1">{formatRatio(s.precision)}</td>
                      <td className="px-3 py-1">{formatRatio(s.recall)}</td>
                      <td className="px-3 py-1">{s.f1 ?? "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
