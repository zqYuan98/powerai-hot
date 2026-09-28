import Link from "next/link";

import { ItemCardView } from "@/components/feed/ItemCard";
import { Card } from "@/components/ui";
import type { DigestDetail } from "@/lib/types";

/** 报纸式日报：刊头 → 看点 → 头条 → 版面目录 → 分版块 → 本期完。 */
export function DigestView({ d }: { d: DigestDetail }) {
  // 头条单独展示，版块里不再重复
  const sections = d.sections
    .map((s) => ({ ...s, items: s.items.filter((i) => i.id !== d.lead?.id) }))
    .filter((s) => s.items.length > 0);
  const minutes = Math.max(1, Math.round((d.stats.items ?? 0) * 0.5));
  return (
    <article>
      <header className="mb-5 border-b-2 border-ink pb-3">
        <p className="text-xs tracking-widest text-muted">{d.kind === "daily" ? "日报" : "周报"} · 第 {d.issue_no} 期</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">{d.title}</h1>
        <p className="mt-2 text-xs text-muted">
          {d.stats.items ?? 0} 条精选 · {d.stats.sources ?? 0} 个信源 · {d.stats.first_party ?? 0} 条一手 ·{" "}
          {d.stats.leads ?? 0} 条商机 · 约 {minutes} 分钟读完
        </p>
      </header>

      {d.overview ? (
        <Card className="mb-5 p-4">
          <h2 className="mb-1 text-sm font-semibold text-ink">今日看点</h2>
          <p className="leading-relaxed text-ink-2">{d.overview}</p>
        </Card>
      ) : null}

      {d.lead ? (
        <section className="mb-6">
          <h2 className="mb-1 text-xs font-semibold tracking-widest text-lead">头条</h2>
          <ItemCardView item={d.lead} showDate />
        </section>
      ) : null}

      {sections.length > 1 ? (
        <nav aria-label="本期版面" className="mb-6 flex flex-wrap gap-2 text-sm">
          {sections.map((s) => (
            <a key={s.name} href={`#sec-${s.name}`} className="rounded-full border border-line px-3 py-1 text-ink-2 hover:bg-surface-2">
              {s.name} <span className="text-muted">{s.items.length}</span>
            </a>
          ))}
        </nav>
      ) : null}

      {sections.length === 0 && !d.lead ? (
        <p className="py-10 text-center text-muted">本期没有精选情报。</p>
      ) : (
        sections.map((s) => (
          <section key={s.name} id={`sec-${s.name}`} className="mb-6 scroll-mt-16">
            <h2 className="border-b border-line pb-1.5 text-base font-semibold text-ink">{s.name}</h2>
            {s.comment ? <p className="mt-2 text-sm text-muted italic">{s.comment}</p> : null}
            <div className="divide-y divide-line">
              {s.items.map((item) => (
                <ItemCardView key={item.id} item={item} showDate />
              ))}
            </div>
          </section>
        ))
      )}
      <p className="py-4 text-center text-sm text-muted">（本期完）</p>
      <p className="text-center">
        <Link href="/daily" className="text-sm text-accent hover:underline">
          往期
        </Link>
      </p>
    </article>
  );
}
