"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Field, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";
import { DOMAIN_LABEL, KTYPE_LABEL } from "@/lib/format";
import type { KnowledgeDetail } from "@/lib/types";

/** 管理员操作：改分类、隐藏/展示（可推翻模型的判断）、重新处理、删除。 */
export function AdminActions({ k }: { k: KnowledgeDetail }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>, after?: () => void) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      if (after) after();
      else router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }
  const patch = (body: object) => run(() => send(`/knowledge/${k.id}`, { method: "PATCH", body }));

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <Field label="专业">
          <select value={k.domain} disabled={busy} onChange={(e) => patch({ domain: e.target.value })} className={inputClass}>
            {Object.entries(DOMAIN_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <Field label="类型">
          <select value={k.ktype} disabled={busy} onChange={(e) => patch({ ktype: e.target.value })} className={inputClass}>
            {Object.entries(KTYPE_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="flex flex-wrap gap-2">
        {k.status === "analyzed" ? (
          <Button className="h-8" disabled={busy} onClick={() => patch({ hidden: true })}>
            隐藏
          </Button>
        ) : ["hidden", "rejected", "duplicate"].includes(k.status) ? (
          <Button className="h-8" variant="primary" disabled={busy} onClick={() => patch({ hidden: false })}>
            仍然展示
          </Button>
        ) : null}
        <Button className="h-8" disabled={busy} onClick={() => run(() => send(`/knowledge/${k.id}/retry`, { body: {} }))}>
          重新处理
        </Button>
        <Button
          className="h-8"
          variant="danger"
          disabled={busy}
          onClick={() => {
            if (!confirm("删除这篇收录？")) return;
            void run(
              () => send(`/knowledge/${k.id}`, { method: "DELETE" }),
              () => router.push("/knowledge"),
            );
          }}
        >
          删除
        </Button>
      </div>
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
