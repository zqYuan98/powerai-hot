"use client";

import { useState } from "react";

import { Button, Card, Field, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";
import { TIER_LABEL } from "@/lib/format";
import type { Tuning } from "@/lib/types";

const DIM_LABEL = {
  relevance: "电力基建相关度",
  opportunity: "商机价值",
  certainty: "确定性",
  timeliness: "时效",
  impact: "影响面",
} as const;
type DimKey = keyof typeof DIM_LABEL;
const TIERS = ["T1", "T1_5", "T2"] as const;

function Num({
  value,
  onChange,
  step = 1,
  min = 0,
  max,
  label,
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  label?: string;
}) {
  return (
    <input
      type="number"
      value={value}
      step={step}
      min={min}
      max={max}
      aria-label={label}
      onChange={(e) => onChange(Number(e.target.value))}
      className={inputClass}
    />
  );
}

export function TuningForm({ initial }: { initial: Tuning }) {
  const [t, setT] = useState<Tuning>(initial);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const weights: Record<DimKey, number> = {
    relevance: 0,
    opportunity: 0,
    certainty: 0,
    timeliness: 0,
    impact: 0,
    ...t.weights,
  };
  const tierCoef = t.tier_coef ?? {};
  const thresholds = t.thresholds ?? {};
  const totalW = Object.values(weights).reduce((a, b) => a + b, 0);

  function update(patch: Partial<Tuning>) {
    setT({ ...t, ...patch });
    setState("idle");
  }

  async function save() {
    setState("saving");
    setError(null);
    try {
      setT(await send<Tuning>("/tuning", { method: "PUT", body: t }));
      setState("saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
      setState("error");
    }
  }

  return (
    <div className="space-y-5">
      <Card className="space-y-3 p-4">
        <h2 className="text-base font-semibold text-ink">业务画像</h2>
        <p className="text-sm text-muted">
          写进初筛与精读提示词，决定「什么算与我相关的商机」。保存后，之后处理的条目立即按新画像判断。
        </p>
        <textarea
          value={t.profile ?? ""}
          onChange={(e) => update({ profile: e.target.value })}
          rows={8}
          aria-label="业务画像"
          className="w-full rounded-md border border-line bg-surface p-3 text-sm leading-relaxed text-ink focus:border-accent focus:outline-none"
        />
        <Field label="日报读者关注点（一句话）">
          <input value={t.focus ?? ""} onChange={(e) => update({ focus: e.target.value })} className={inputClass} />
        </Field>
      </Card>

      <Card className="space-y-3 p-4">
        <h2 className="text-base font-semibold text-ink">打分权重</h2>
        <p className="text-sm text-muted">
          总分 = 各维度（0–10）加权平均 × 10 × 信源档位系数；「包装大于实质」再乘惩罚系数。权重自动归一化（当前合计{" "}
          {totalW.toFixed(2)}）。
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {(Object.keys(DIM_LABEL) as DimKey[]).map((k) => (
            <Field key={k} label={DIM_LABEL[k]}>
              <Num
                value={weights[k]}
                step={0.05}
                onChange={(v) => update({ weights: { ...weights, [k]: v } })}
              />
            </Field>
          ))}
        </div>
      </Card>

      <Card className="space-y-3 p-4">
        <h2 className="text-base font-semibold text-ink">信源档位</h2>
        <p className="text-sm text-muted">一手信源（政府 / 电网 / 招标平台）系数更高、精选门槛更低；媒体转载反之。</p>
        <div className="overflow-x-auto">
          <table className="text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="pr-4 pb-1 font-medium">档位</th>
                <th className="pr-4 pb-1 font-medium">分数系数</th>
                <th className="pb-1 font-medium">精选门槛</th>
              </tr>
            </thead>
            <tbody>
              {TIERS.map((tier) => (
                <tr key={tier}>
                  <td className="py-1 pr-4 whitespace-nowrap text-ink-2">
                    {tier} · {TIER_LABEL[tier]}
                  </td>
                  <td className="w-28 py-1 pr-4">
                    <Num
                      label={`${tier} 分数系数`}
                      value={tierCoef[tier] ?? 1}
                      step={0.05}
                      onChange={(v) => update({ tier_coef: { ...tierCoef, [tier]: v } })}
                    />
                  </td>
                  <td className="w-28 py-1">
                    <Num
                      label={`${tier} 精选门槛`}
                      value={thresholds[tier] ?? 70}
                      max={100}
                      onChange={(v) => update({ thresholds: { ...thresholds, [tier]: v } })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="grid gap-3 p-4 sm:grid-cols-3">
        <Field label="包装大于实质惩罚系数">
          <Num value={t.hype_penalty ?? 0.7} step={0.05} max={1} onChange={(v) => update({ hype_penalty: v })} />
        </Field>
        <Field label="商机匹配度 ≥ 此值即推送">
          <Num value={t.lead_notify_min_match ?? 60} max={100} onChange={(v) => update({ lead_notify_min_match: v })} />
        </Field>
        <Field label="事件归并相似度（0–1）">
          <Num value={t.story_similarity ?? 0.86} step={0.01} max={1} onChange={(v) => update({ story_similarity: v })} />
        </Field>
      </Card>

      <div className="sticky bottom-[calc(4rem+env(safe-area-inset-bottom))] flex items-center justify-end gap-3 md:bottom-4">
        {state === "saved" ? <span className="text-sm text-ok">已保存</span> : null}
        {error ? <span className="text-sm text-danger">{error}</span> : null}
        <Button variant="primary" onClick={save} disabled={state === "saving"}>
          {state === "saving" ? "保存中…" : "保存设置"}
        </Button>
      </div>
    </div>
  );
}
