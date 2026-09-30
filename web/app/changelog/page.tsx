import { ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { MarkChangelogSeen } from "@/components/MarkChangelogSeen";
import { AsideCard, ReadingLayout } from "@/components/ui";
import changelog from "@/content/changelog.json";
import { cn } from "@/lib/cn";

export const metadata: Metadata = {
  title: "更新日志",
  description: "电力基建情报站的功能更新、优化与公告。",
};

type Release = (typeof changelog.releases)[number];

const KIND_DOT: Record<string, string> = {
  更新: "bg-accent",
  优化: "bg-ok",
  公告: "bg-lead",
  下线: "bg-muted",
};

/** 正文：普通行是段落，以「- 」开头的连续行合成一个列表。 */
function Body({ lines }: { lines: string[] }) {
  const blocks: (string | string[])[] = [];
  for (const line of lines) {
    const last = blocks.at(-1);
    if (!line.startsWith("- ")) blocks.push(line);
    else if (Array.isArray(last)) last.push(line.slice(2));
    else blocks.push([line.slice(2)]);
  }
  return blocks.map((b, i) =>
    Array.isArray(b) ? (
      <ul key={i} className="mt-2 space-y-1">
        {b.map((li, j) => (
          <li key={j} className="flex gap-2">
            <span className="mt-2 size-1 shrink-0 rounded-full bg-muted" aria-hidden />
            <span>{li}</span>
          </li>
        ))}
      </ul>
    ) : (
      <p key={i} className="mt-2">
        {b}
      </p>
    ),
  );
}

export default function ChangelogPage() {
  const byDate = new Map<string, Release[]>();
  for (const r of changelog.releases) byDate.set(r.date, [...(byDate.get(r.date) ?? []), r]);

  return (
    <ReadingLayout
      aside={
        <AsideCard title="有想法或遇到问题">
          <p className="text-[13px] leading-relaxed text-muted">想要的功能、想加的信源、用着不顺的地方，都可以在反馈页告诉我们。</p>
          <Link href="/feedback?from=/changelog" className="mt-2 inline-flex items-center gap-0.5 text-sm font-medium text-accent hover:underline">
            去反馈 <ChevronRight className="size-4" aria-hidden />
          </Link>
        </AsideCard>
      }
    >
      <MarkChangelogSeen />
      <h1 className="text-xl font-semibold tracking-tight text-ink">更新日志</h1>
      <p className="mt-1 text-sm text-muted">功能更新、优化与公告，最新的在最上面。</p>
      <div className="mt-6 space-y-8">
        {[...byDate.entries()].map(([date, releases]) => (
          <section key={date} aria-labelledby={`d-${date}`} className="grid gap-2 sm:grid-cols-[7rem_minmax(0,1fr)]">
            <h2 id={`d-${date}`} className="pt-0.5 text-sm font-medium text-muted tabular-nums">
              {date}
            </h2>
            <div className="space-y-6">
              {releases.map((r) => (
                <article key={`${r.date}-${r.time}`}>
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <span className={cn("size-1.5 rounded-full", KIND_DOT[r.kind] ?? "bg-muted")} aria-hidden />
                    {r.kind}
                    <span className="tabular-nums">{r.time}</span>
                  </div>
                  <h3 className="mt-1 font-semibold text-ink">{r.title}</h3>
                  <div className="text-sm leading-relaxed text-ink-2">
                    <Body lines={r.body} />
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </ReadingLayout>
  );
}
