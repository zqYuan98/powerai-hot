import type { Metadata } from "next";
import Link from "next/link";

import { DigestView } from "@/components/DigestView";
import { Empty, TabLinks } from "@/components/ui";
import { api, apiOptional } from "@/lib/api.server";
import type { DigestBrief, DigestDetail } from "@/lib/types";

export const metadata: Metadata = { title: "日报" };

export default async function DailyPage({ searchParams }: { searchParams: Promise<{ kind?: string }> }) {
  const kind = (await searchParams).kind === "weekly" ? "weekly" : "daily";
  const [latest, archive] = await Promise.all([
    apiOptional<DigestDetail>(`/digests/${kind}/latest`),
    api<DigestBrief[]>("/digests", { kind, limit: 60 }),
  ]);
  const byMonth = new Map<string, DigestBrief[]>();
  for (const d of archive.slice(1)) {
    const key = d.period_start.slice(0, 7);
    byMonth.set(key, [...(byMonth.get(key) ?? []), d]);
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_260px]">
      <div className="min-w-0">
        <TabLinks
          active={kind}
          tabs={[
            { key: "daily", href: "/daily", label: "日报" },
            { key: "weekly", href: "/daily?kind=weekly", label: "周报" },
          ]}
        />
        {latest ? (
          <DigestView d={latest} />
        ) : (
          <Empty title={kind === "daily" ? "还没有日报" : "还没有周报"}>
            {kind === "daily" ? "每天 08:00 自动生成，覆盖前一天 08:00 至当天 08:00。" : "每周一 08:30 自动生成。"}
          </Empty>
        )}
      </div>
      <aside>
        <h2 className="mb-2 text-sm font-semibold text-ink">往期</h2>
        {byMonth.size === 0 ? <p className="text-sm text-muted">暂无</p> : null}
        {[...byMonth.entries()].map(([month, items]) => (
          <div key={month} className="mb-4">
            <h3 className="mb-1 text-xs text-muted">{month.replace("-", " 年 ")} 月</h3>
            <ul className="space-y-1">
              {items.map((d) => (
                <li key={d.id}>
                  <Link href={`/daily/${d.kind}/${d.period_start}`} className="block rounded px-2 py-1 text-sm hover:bg-surface-2">
                    <span className="text-muted tabular-nums">{d.period_start.slice(5)}</span>{" "}
                    <span className="text-ink-2">{d.lead_title ?? `${d.item_count} 条精选`}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>
    </div>
  );
}
