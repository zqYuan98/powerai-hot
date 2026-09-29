import type { Metadata } from "next";

import { Card, Empty } from "@/components/ui";
import { api } from "@/lib/api.server";
import { formatDateTime } from "@/lib/format";
import type { UsageOut } from "@/lib/types";

export const metadata: Metadata = { title: "模型用量" };

const TASK_LABEL: Record<string, string> = {
  screen: "初筛",
  analyze: "精读",
  story_digest: "事件综述",
  digest_daily: "日报",
  digest_weekly: "周报",
  embed: "向量",
  "eval:screen": "评测·初筛",
  "eval:analyze": "评测·精读",
};

export default async function UsagePage() {
  const usage = await api<UsageOut>("/usage", { days: 14 });
  const total = usage.days.reduce(
    (acc, d) => ({ calls: acc.calls + d.calls, fail: acc.fail + d.failures, cost: acc.cost + d.cost_yuan }),
    { calls: 0, fail: 0, cost: 0 },
  );

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-3">
          <div className="font-mono text-2xl font-semibold text-ink tabular-nums">{total.calls}</div>
          <div className="text-xs text-muted">14 天调用</div>
        </Card>
        <Card className="p-3">
          <div className={`font-mono text-2xl font-semibold tabular-nums ${total.fail ? "text-danger" : "text-ink"}`}>
            {total.fail}
          </div>
          <div className="text-xs text-muted">失败</div>
        </Card>
        <Card className="p-3">
          <div className="font-mono text-2xl font-semibold text-ink tabular-nums">¥{total.cost.toFixed(2)}</div>
          <div className="text-xs text-muted">估算费用（按配置单价）</div>
        </Card>
      </div>

      {usage.days.length === 0 ? (
        <Empty title="暂无模型调用记录" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">日期</th>
                <th className="px-3 py-2 font-medium">任务</th>
                <th className="px-3 py-2 text-right font-medium">调用</th>
                <th className="px-3 py-2 text-right font-medium">失败</th>
                <th className="px-3 py-2 text-right font-medium">输入 tokens</th>
                <th className="px-3 py-2 text-right font-medium">输出 tokens</th>
                <th className="px-3 py-2 text-right font-medium">费用</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line tabular-nums">
              {usage.days.map((d) => (
                <tr key={`${d.day}-${d.task}`}>
                  <td className="px-3 py-1.5 text-ink-2">{d.day}</td>
                  <td className="px-3 py-1.5 text-ink">{TASK_LABEL[d.task] ?? d.task}</td>
                  <td className="px-3 py-1.5 text-right">{d.calls}</td>
                  <td className={`px-3 py-1.5 text-right ${d.failures ? "text-danger" : "text-muted"}`}>{d.failures}</td>
                  <td className="px-3 py-1.5 text-right text-ink-2">{d.prompt_tokens.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right text-ink-2">{d.completion_tokens.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right">¥{d.cost_yuan.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {usage.recent_errors.length ? (
        <section>
          <h2 className="mb-2 text-base font-semibold text-ink">最近错误</h2>
          <ul className="space-y-1.5 text-sm">
            {usage.recent_errors.map((e, i) => (
              <li key={i} className="rounded-md bg-danger-soft px-3 py-2 text-danger">
                <span className="mr-2 text-xs opacity-80">
                  {formatDateTime(String(e.created_at))} · {TASK_LABEL[String(e.task)] ?? String(e.task)} · {String(e.model)}
                </span>
                {String(e.error)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
