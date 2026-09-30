import { ArrowLeft, ExternalLink } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { NoteEditor } from "@/components/feed/NoteEditor";
import { AdminActions } from "@/components/knowledge/AdminActions";
import { KnowledgeCardView, KnowledgeMeta } from "@/components/knowledge/KnowledgeCard";
import { Card } from "@/components/ui";
import { api } from "@/lib/api.server";
import { formatDateTime } from "@/lib/format";
import type { KnowledgeDetail } from "@/lib/types";
import { isAdmin } from "@/lib/viewer";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const k = await api<KnowledgeDetail>(`/knowledge/${(await params).id}`);
  return { title: k.title, description: k.summary ?? undefined };
}

const DIMS: { key: keyof KnowledgeDetail["dims"]; label: string }[] = [
  { key: "depth", label: "深度" },
  { key: "practical", label: "实用性" },
  { key: "accuracy", label: "准确性" },
  { key: "originality", label: "原创性" },
];

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-sm font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

export default async function KnowledgeDetailPage({ params }: Props) {
  const [k, admin] = await Promise.all([api<KnowledgeDetail>(`/knowledge/${(await params).id}`), isAdmin()]);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <article className="min-w-0">
        <Link href="/knowledge" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden />
          知识库
        </Link>
        <KnowledgeMeta k={k} className="mb-2" />
        <h1 className="text-2xl leading-snug font-semibold tracking-tight text-ink">{k.title}</h1>
        {k.original_title !== k.title ? <p className="mt-1 text-sm text-muted">原题：{k.original_title}</p> : null}
        {admin && k.status_reason ? (
          <p className="mt-3 rounded-md bg-surface-2 px-3 py-2 text-sm text-ink-2">
            {k.status_reason}
            {k.duplicate_of ? (
              <>
                {" "}
                <Link href={`/knowledge/${k.duplicate_of}`} className="text-accent hover:underline">
                  查看原收录
                </Link>
              </>
            ) : null}
          </p>
        ) : null}

        {k.summary ? (
          <Card className="mt-4 p-4">
            <p className="leading-relaxed text-ink">{k.summary}</p>
          </Card>
        ) : null}

        {k.key_points.length ? (
          <Block title="核心要点">
            <ol className="space-y-2">
              {k.key_points.map((p, i) => (
                <li key={p} className="flex gap-3 text-[15px] leading-relaxed text-ink">
                  <span className="mt-0.5 font-mono text-xs font-semibold text-accent tabular-nums">{String(i + 1).padStart(2, "0")}</span>
                  <span>{p}</span>
                </li>
              ))}
            </ol>
          </Block>
        ) : null}

        {k.scenarios || k.solution_use ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {k.scenarios ? (
              <Card className="p-4">
                <h2 className="mb-1 text-xs font-medium text-muted">适用场景</h2>
                <p className="text-sm leading-relaxed text-ink">{k.scenarios}</p>
              </Card>
            ) : null}
            {k.solution_use ? (
              <Card className="p-4">
                <h2 className="mb-1 text-xs font-medium text-muted">可用于方案</h2>
                <p className="text-sm leading-relaxed text-ink">{k.solution_use}</p>
              </Card>
            ) : null}
          </div>
        ) : null}

        {k.standards.length ? (
          <Block title="涉及标准">
            <div className="flex flex-wrap gap-2">
              {k.standards.map((s) => (
                <Link
                  key={s}
                  href={`/knowledge?q=${encodeURIComponent(s)}`}
                  className="rounded-md border border-line bg-surface px-2 py-1 font-mono text-xs text-ink-2 hover:border-accent hover:text-accent"
                >
                  {s}
                </Link>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-muted">编号均在原文中出现过；具体条款请以现行有效版本为准。</p>
          </Block>
        ) : null}

        <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-line pt-4">
          <a
            href={k.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-accent px-4 text-sm font-medium text-white hover:opacity-90"
          >
            阅读原文 <ExternalLink className="size-3.5" aria-hidden />
          </a>
          <span className="text-xs text-muted">要点由 AI 根据原文提炼，引用前请核对原文。版权归原作者所有。</span>
        </div>

        {admin && k.content_text ? (
          <details className="mt-6 rounded-lg border border-line bg-surface p-4">
            <summary className="cursor-pointer text-sm font-medium text-ink">原文全文（仅自己可见）</summary>
            <div className="prose-article mt-3 text-sm whitespace-pre-line">{k.content_text}</div>
          </details>
        ) : null}
      </article>

      <aside className="space-y-4">
        {admin ? (
          <Card className="space-y-4 p-4">
            <h2 className="text-sm font-semibold text-ink">管理</h2>
            <NoteEditor endpoint={`/knowledge/${k.id}`} field="note" initial={k.note} placeholder="收录备注：为什么收、给哪个项目用…" />
            <AdminActions k={k} />
            <p className="text-xs text-muted">收录于 {formatDateTime(k.created_at)}</p>
          </Card>
        ) : null}

        {k.score !== null ? (
          <Card className="p-4">
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold text-ink">质量评分</h2>
              <span className="font-mono text-lg font-semibold text-ink tabular-nums">{Math.round(k.score)}</span>
            </div>
            <ul className="space-y-1.5">
              {DIMS.map((d) => {
                const v = k.dims[d.key] ?? 0;
                return (
                  <li key={d.key} className="flex items-center gap-2 text-xs">
                    <span className="w-14 shrink-0 text-muted">{d.label}</span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                      <span className="block h-full rounded-full bg-accent" style={{ width: `${v * 10}%` }} />
                    </span>
                    <span className="w-5 text-right font-mono text-ink-2 tabular-nums">{v}</span>
                  </li>
                );
              })}
            </ul>
          </Card>
        ) : null}

        {k.tags.length ? (
          <Card className="p-4">
            <h2 className="mb-2 text-sm font-semibold text-ink">关键词</h2>
            <div className="flex flex-wrap gap-1.5">
              {k.tags.map((t) => (
                <Link key={t} href={`/knowledge?q=${encodeURIComponent(t)}`} className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-ink-2 hover:text-accent">
                  {t}
                </Link>
              ))}
            </div>
          </Card>
        ) : null}

        {k.related.length ? (
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-ink">相关知识</h2>
            <div className="divide-y divide-line">
              {k.related.map((r) => (
                <KnowledgeCardView key={r.id} k={r} compact />
              ))}
            </div>
          </Card>
        ) : null}
      </aside>
    </div>
  );
}
