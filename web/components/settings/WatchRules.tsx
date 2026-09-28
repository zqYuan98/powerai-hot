"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge, Button, Card, Field, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";
import { CHANNEL_LABEL, CHANNELS } from "@/lib/format";
import type { Channel, WatchRuleIn, WatchRuleOut } from "@/lib/types";

type Draft = Required<WatchRuleIn>;

const EMPTY: Draft = {
  name: "",
  keywords: [],
  provinces: [],
  channels: [],
  min_amount_wan: null,
  min_voltage_kv: null,
  notify: true,
  enabled: true,
};

const split = (v: string) =>
  v
    .split(/[,，、\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);

function RuleForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: Draft;
  onSave: (r: Draft) => Promise<void>;
  onCancel: () => void;
}) {
  const [rule, setRule] = useState(initial);
  const [keywords, setKeywords] = useState(initial.keywords.join("，"));
  const [provinces, setProvinces] = useState(initial.provinces.join("，"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <Card className="space-y-3 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="规则名">
          <input value={rule.name} onChange={(e) => setRule({ ...rule, name: e.target.value })} className={inputClass} />
        </Field>
        <Field label="关键词（任一命中，逗号分隔）">
          <input
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            className={inputClass}
            placeholder="布控球，无人机巡检"
          />
        </Field>
        <Field label="省份（留空为全国）">
          <input
            value={provinces}
            onChange={(e) => setProvinces(e.target.value)}
            className={inputClass}
            placeholder="广东，广西"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="金额 ≥（万元）">
            <input
              type="number"
              min={0}
              value={rule.min_amount_wan ?? ""}
              onChange={(e) => setRule({ ...rule, min_amount_wan: e.target.value === "" ? null : e.target.value })}
              className={inputClass}
            />
          </Field>
          <Field label="电压 ≥（kV）">
            <input
              type="number"
              min={0}
              value={rule.min_voltage_kv ?? ""}
              onChange={(e) =>
                setRule({ ...rule, min_voltage_kv: e.target.value === "" ? null : Number(e.target.value) })
              }
              className={inputClass}
            />
          </Field>
        </div>
      </div>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-muted">频道（留空为全部）</legend>
        <div className="flex flex-wrap gap-2">
          {CHANNELS.map((c) => {
            const on = rule.channels.includes(c.value);
            return (
              <label key={c.value} className="flex items-center gap-1 text-sm text-ink-2">
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() =>
                    setRule({
                      ...rule,
                      channels: on ? rule.channels.filter((x) => x !== c.value) : [...rule.channels, c.value],
                    })
                  }
                  className="size-4 accent-accent"
                />
                {c.label}
              </label>
            );
          })}
        </div>
      </fieldset>
      <div className="flex flex-wrap items-center gap-4 text-sm text-ink-2">
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={rule.enabled}
            onChange={(e) => setRule({ ...rule, enabled: e.target.checked })}
            className="size-4 accent-accent"
          />
          启用
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={rule.notify}
            onChange={(e) => setRule({ ...rule, notify: e.target.checked })}
            className="size-4 accent-accent"
          />
          飞书推送
        </label>
        {error ? <span className="text-danger">{error}</span> : null}
        <span className="ml-auto flex gap-2">
          <Button variant="ghost" onClick={onCancel}>
            取消
          </Button>
          <Button
            variant="primary"
            disabled={busy || !rule.name.trim()}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                await onSave({ ...rule, keywords: split(keywords), provinces: split(provinces) });
              } catch (e) {
                setError(e instanceof Error ? e.message : "保存失败");
                setBusy(false);
              }
            }}
          >
            保存
          </Button>
        </span>
      </div>
    </Card>
  );
}

export function WatchRules({ initial }: { initial: WatchRuleOut[] }) {
  const [rules, setRules] = useState(initial);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(id: number | "new", body: Draft) {
    const saved =
      id === "new"
        ? await send<WatchRuleOut>("/watch-rules", { body })
        : await send<WatchRuleOut>(`/watch-rules/${id}`, { method: "PUT", body });
    setRules((prev) => (id === "new" ? [...prev, saved] : prev.map((r) => (r.id === id ? saved : r))));
    setEditing(null);
  }

  async function remove(id: number) {
    try {
      await send(`/watch-rules/${id}`, { method: "DELETE" });
      setRules((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  }

  return (
    <div className="space-y-3">
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {rules.map((r) =>
        editing === r.id ? (
          <RuleForm key={r.id} initial={r} onSave={(b) => save(r.id, b)} onCancel={() => setEditing(null)} />
        ) : (
          <Card key={r.id} className="flex flex-wrap items-start gap-3 p-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-ink">{r.name}</span>
                {!r.enabled ? <Badge className="tone-muted">已停用</Badge> : null}
                {r.enabled && !r.notify ? <Badge className="tone-muted">不推送</Badge> : null}
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
                {r.keywords.map((k) => (
                  <Badge key={k} className="tone-tech">
                    {k}
                  </Badge>
                ))}
                {r.provinces.length ? <Badge className="tone-muted">{r.provinces.join("、")}</Badge> : null}
                {r.channels.map((c) => (
                  <Badge key={c} className="tone-muted">
                    {CHANNEL_LABEL[c as Channel]}
                  </Badge>
                ))}
                {r.min_amount_wan ? <Badge className="tone-lead">≥ {r.min_amount_wan} 万元</Badge> : null}
                {r.min_voltage_kv ? <Badge className="tone-lead">≥ {r.min_voltage_kv}kV</Badge> : null}
              </div>
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" className="h-8 px-2" onClick={() => setEditing(r.id)} aria-label={`编辑 ${r.name}`}>
                <Pencil className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                className="h-8 px-2 text-danger"
                onClick={() => remove(r.id)}
                aria-label={`删除 ${r.name}`}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </Card>
        ),
      )}
      {editing === "new" ? (
        <RuleForm initial={EMPTY} onSave={(b) => save("new", b)} onCancel={() => setEditing(null)} />
      ) : (
        <Button onClick={() => setEditing("new")}>
          <Plus className="size-4" /> 新建规则
        </Button>
      )}
    </div>
  );
}
