import type { Metadata } from "next";
import Link from "next/link";

import { DeadlineBadge, ScoreBadge } from "@/components/feed/ItemCard";
import { FollowControl } from "@/components/leads/FollowControl";
import { Badge, Empty, Field, inputClass, PageHeader } from "@/components/ui";
import { api } from "@/lib/api.server";
import { BIZ_LABEL, CHANNEL_LABEL, FOLLOW_LABEL, formatAmount, formatDate, STAGE_LABEL } from "@/lib/format";
import type { LeadPage, LeadRow } from "@/lib/types";

export const metadata: Metadata = { title: "商机" };

type SP = Record<string, string | undefined>;
const PAGE = 50;
const SORTS = { recent: "最新发现", deadline: "截止最近", amount: "金额最大", match: "匹配度最高" } as const;

function LeadCells({ row }: { row: LeadRow }) {
  const { item, lead } = row;
  return (
    <>
      <Link href={`/items/${item.id}`} className="font-medium text-ink after:absolute after:inset-0 hover:text-accent">
        {item.title_zh || item.title}
      </Link>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span>{item.source.name}</span>
        <span>{formatDate(item.first_seen_at)}</span>
        <Badge className="tone-lead">{CHANNEL_LABEL[item.channel]}</Badge>
        {lead.biz_line !== "other" ? <Badge className="tone-tech">{BIZ_LABEL[lead.biz_line]}</Badge> : null}
        {lead.owner ? <span className="max-w-[20em] truncate">业主：{lead.owner}</span> : null}
      </div>
    </>
  );
}

export default async function LeadsPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const offset = Math.max(0, Number(sp.offset ?? 0) || 0);
  const sort = (sp.sort && sp.sort in SORTS ? sp.sort : "recent") as keyof typeof SORTS;
  const [data, provinces] = await Promise.all([
    api<LeadPage>("/leads", {
      q: sp.q,
      stage: sp.stage,
      province: sp.province,
      biz_line: sp.biz_line,
      follow: sp.follow,
      min_amount_wan: sp.min_amount_wan,
      min_voltage_kv: sp.min_voltage_kv,
      open_only: sp.open_only === "1" ? true : undefined,
      sort,
      offset,
      limit: PAGE,
    }),
    api<string[]>("/leads/provinces"),
  ]);
  const pageHref = (o: number) => {
    const p = new URLSearchParams(Object.entries(sp).filter((e): e is [string, string] => !!e[1]));
    p.set("offset", String(o));
    return `/leads?${p}`;
  };

  return (
    <>
      <PageHeader title="商机" desc={`招标、中标、项目核准与规划中抽取的结构化线索 · 共 ${data.total} 条`} />

      <form className="mb-5 grid grid-cols-2 gap-3 rounded-lg border border-line bg-surface p-3 sm:grid-cols-4 lg:grid-cols-8" method="get">
        <Field label="关键词" className="col-span-2">
          <input name="q" defaultValue={sp.q} placeholder="项目名 / 业主 / 标题" className={inputClass} />
        </Field>
        <Field label="阶段">
          <select name="stage" defaultValue={sp.stage ?? ""} className={inputClass}>
            <option value="">全部</option>
            {Object.entries(STAGE_LABEL)
              .filter(([k]) => k !== "unknown")
              .map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
          </select>
        </Field>
        <Field label="省份">
          <select name="province" defaultValue={sp.province ?? ""} className={inputClass}>
            <option value="">全国</option>
            {provinces.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </Field>
        <Field label="业务线">
          <select name="biz_line" defaultValue={sp.biz_line ?? ""} className={inputClass}>
            <option value="">全部</option>
            {Object.entries(BIZ_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>
        <Field label="跟进">
          <select name="follow" defaultValue={sp.follow ?? ""} className={inputClass}>
            <option value="">未忽略的</option>
            {Object.entries(FOLLOW_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>
        <Field label="金额 ≥（万元）">
          <input name="min_amount_wan" type="number" min={0} defaultValue={sp.min_amount_wan} className={inputClass} />
        </Field>
        <Field label="电压 ≥（kV）">
          <select name="min_voltage_kv" defaultValue={sp.min_voltage_kv ?? ""} className={inputClass}>
            <option value="">不限</option>
            {[35, 110, 220, 500, 1000].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </Field>
        <Field label="排序">
          <select name="sort" defaultValue={sort} className={inputClass}>
            {Object.entries(SORTS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </Field>
        <label className="col-span-2 flex items-center gap-2 self-end pb-2 text-sm text-ink-2">
          <input type="checkbox" name="open_only" value="1" defaultChecked={sp.open_only === "1"} className="size-4 accent-accent" />
          只看未截止
        </label>
        <div className="col-span-2 flex items-end gap-2 sm:col-span-4 lg:col-span-6 lg:justify-end">
          <Link href="/leads" className="flex h-9 items-center rounded-md px-3 text-sm text-muted hover:text-ink">
            重置
          </Link>
          <button type="submit" className="h-9 rounded-md bg-accent px-4 text-sm font-medium text-white hover:opacity-90">
            筛选
          </button>
        </div>
      </form>

      {data.items.length === 0 ? (
        <Empty title="没有符合条件的商机">放宽筛选条件，或等待下一轮采集。</Empty>
      ) : (
        <>
          {/* 桌面：表格 */}
          <div className="hidden overflow-x-auto rounded-lg border border-line bg-surface md:block">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs text-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">项目</th>
                  <th className="px-3 py-2 font-medium whitespace-nowrap">阶段</th>
                  <th className="px-3 py-2 font-medium whitespace-nowrap">地区</th>
                  <th className="px-3 py-2 text-right font-medium whitespace-nowrap">金额</th>
                  <th className="px-3 py-2 text-right font-medium whitespace-nowrap">电压</th>
                  <th className="px-3 py-2 font-medium whitespace-nowrap">截止</th>
                  <th className="px-3 py-2 text-right font-medium whitespace-nowrap">匹配</th>
                  <th className="px-3 py-2 font-medium whitespace-nowrap">跟进</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((row) => (
                  <tr key={row.item.id} className="align-top hover:bg-surface-2/60">
                    <td className="relative max-w-md px-3 py-2.5">
                      <LeadCells row={row} />
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-ink-2">{STAGE_LABEL[row.lead.stage]}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-ink-2">{row.lead.province ?? "—"}</td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap text-ink tabular-nums">
                      {formatAmount(row.lead.amount_wan) ?? "—"}
                    </td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap text-ink-2 tabular-nums">
                      {row.lead.voltage_kv ? `${row.lead.voltage_kv}kV` : "—"}
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {row.lead.deadline_at ? (
                        <div className="flex flex-col gap-1">
                          <span className="text-xs text-ink-2">{formatDate(row.lead.deadline_at)}</span>
                          <DeadlineBadge iso={row.lead.deadline_at} />
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <ScoreBadge score={row.lead.match_score} />
                    </td>
                    <td className="px-3 py-2.5">
                      <FollowControl itemId={row.item.id} status={row.lead.follow_status} compact />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 移动：卡片 */}
          <div className="divide-y divide-line md:hidden">
            {data.items.map((row) => (
              <div key={row.item.id} className="relative py-3">
                <LeadCells row={row} />
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-2">
                  <Badge className="tone-lead">{STAGE_LABEL[row.lead.stage]}</Badge>
                  {formatAmount(row.lead.amount_wan) ? (
                    <span className="font-medium text-ink">{formatAmount(row.lead.amount_wan)}</span>
                  ) : null}
                  {row.lead.voltage_kv ? <span>{row.lead.voltage_kv}kV</span> : null}
                  {row.lead.province ? <span>{row.lead.province}</span> : null}
                  <DeadlineBadge iso={row.lead.deadline_at} />
                  <span className="ml-auto">
                    <FollowControl itemId={row.item.id} status={row.lead.follow_status} compact />
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-muted">
              第 {offset + 1}–{offset + data.items.length} 条，共 {data.total} 条
            </span>
            <div className="flex gap-2">
              {offset > 0 ? (
                <Link href={pageHref(Math.max(0, offset - PAGE))} className="rounded-md border border-line px-3 py-1.5 hover:bg-surface-2">
                  上一页
                </Link>
              ) : null}
              {offset + PAGE < data.total ? (
                <Link href={pageHref(offset + PAGE)} className="rounded-md border border-line px-3 py-1.5 hover:bg-surface-2">
                  下一页
                </Link>
              ) : null}
            </div>
          </div>
        </>
      )}
    </>
  );
}
