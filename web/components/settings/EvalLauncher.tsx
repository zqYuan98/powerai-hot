"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Field, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";
import type { Ok } from "@/lib/types";

const MODES = [
  { value: "stored", label: "线上已有判断（免费）" },
  { value: "rerun", label: "用当前提示词和参数重跑（调模型）" },
] as const;
const SPLITS = [
  { value: "development", label: "开发集" },
  { value: "holdout", label: "留出集" },
  { value: "all", label: "全部" },
] as const;

export function EvalLauncher({ labeled }: { labeled: number }) {
  const router = useRouter();
  const [mode, setMode] = useState<(typeof MODES)[number]["value"]>("stored");
  const [split, setSplit] = useState<(typeof SPLITS)[number]["value"]>("development");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function start() {
    if (mode === "rerun" && !confirm(`重跑会对约 ${labeled} 条样本调用模型（约每条 ¥0.005–0.01），继续？`)) return;
    setBusy(true);
    try {
      const r = await send<Ok>("/eval-runs", {
        body: { mode, split, label: label || null },
      });
      setMsg(r.detail ?? "已加入队列");
      router.refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "提交失败");
    } finally {
      setBusy(false);
    }
  }

  const select =
    "h-9 rounded-md border border-line bg-surface px-2 text-sm text-ink focus:border-accent focus:outline-none";
  return (
    <div className="flex flex-wrap items-end gap-3">
      <Field label="评测方式">
        <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)} className={select}>
          {MODES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="样本">
        <select value={split} onChange={(e) => setSplit(e.target.value as typeof split)} className={select}>
          {SPLITS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="说明（可选）" className="min-w-48 flex-1">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="如：第一版评分标准"
          className={inputClass}
        />
      </Field>
      <Button variant="primary" disabled={busy || labeled === 0} onClick={() => void start()}>
        开始评测
      </Button>
      {msg ? <p className="w-full text-sm text-ink-2">{msg}</p> : null}
    </div>
  );
}
