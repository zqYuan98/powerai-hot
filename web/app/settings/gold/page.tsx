import type { Metadata } from "next";
import Link from "next/link";

import { EvalLauncher } from "@/components/settings/EvalLauncher";
import { GoldLabeler } from "@/components/settings/GoldLabeler";
import { Card, Empty } from "@/components/ui";
import { api, apiOptional } from "@/lib/api.server";
import { EVAL_MODE_LABEL, EVAL_SPLIT_LABEL, formatDateTime, formatRatio } from "@/lib/format";
import type { EvalRunBrief, GoldCase, GoldStats } from "@/lib/types";

export const metadata: Metadata = { title: "精选校准" };

export default async function GoldPage() {
  const [stats, next, runs] = await Promise.all([
    api<GoldStats>("/gold/stats"),
    apiOptional<GoldCase>("/gold/next"), // 标完了返回 null
    api<EvalRunBrief[]>("/eval-runs"),
  ]);

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h2 className="text-base font-semibold text-ink">标注</h2>
        <p className="text-sm text-muted">
          逐条判断「这条该不该进精选」。为了不被系统的判断带偏，这里只给原文，不显示 AI 的分数、摘要和结论。
          抽样偏向差一点入选、差一点落选的难例；约 1/5 自动留作留出集，调提示词时只看开发集，最后再用留出集检查。
        </p>
        <GoldLabeler initialCase={next} initialStats={stats} />
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-ink">评测</h2>
        <p className="text-sm text-muted">
          「线上已有判断」直接用库里的结果，不花钱，作为基线；改了提示词或打分参数后，用「重跑」在同一批样本上对比。
          先看判错的条目改评分标准，最后才动门槛：门槛只能整体移动，解决不了「哪一类判错了」。
        </p>
        <Card className="p-4">
          <EvalLauncher labeled={stats.total} />
        </Card>
        {runs.length === 0 ? (
          <Empty title="还没有评测记录">标注几十条以后就可以先跑一次「线上已有判断」看看基线。</Empty>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="border-b border-line text-left text-xs text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">#</th>
                  <th className="px-3 py-2 font-medium">说明</th>
                  <th className="px-3 py-2 font-medium">方式 · 样本</th>
                  <th className="px-3 py-2 text-right font-medium">计入</th>
                  <th className="px-3 py-2 text-right font-medium">查准</th>
                  <th className="px-3 py-2 text-right font-medium">查全</th>
                  <th className="px-3 py-2 text-right font-medium">F1</th>
                  <th className="px-3 py-2 text-right font-medium">花费</th>
                  <th className="px-3 py-2 font-medium">时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line tabular-nums">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-surface-2">
                    <td className="px-3 py-1.5 text-muted">{r.id}</td>
                    <td className="px-3 py-1.5">
                      <Link href={`/settings/gold/${r.id}`} className="text-ink hover:text-accent">
                        {r.label}
                      </Link>
                      {r.status !== "done" ? (
                        <span className={r.status === "failed" ? "ml-2 text-danger" : "ml-2 text-accent"}>
                          {r.status === "failed" ? "失败" : "进行中"}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-1.5 text-ink-2">
                      {EVAL_MODE_LABEL[r.mode] ?? r.mode} · {EVAL_SPLIT_LABEL[r.split] ?? r.split}
                    </td>
                    <td className="px-3 py-1.5 text-right">{String(r.metrics.n ?? "–")}</td>
                    <td className="px-3 py-1.5 text-right">{formatRatio(r.metrics.precision)}</td>
                    <td className="px-3 py-1.5 text-right">{formatRatio(r.metrics.recall)}</td>
                    <td className="px-3 py-1.5 text-right">{String(r.metrics.f1 ?? "–")}</td>
                    <td className="px-3 py-1.5 text-right text-ink-2">
                      {r.cost_yuan ? `¥${r.cost_yuan.toFixed(3)}` : "–"}
                    </td>
                    <td className="px-3 py-1.5 text-ink-2">{formatDateTime(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
