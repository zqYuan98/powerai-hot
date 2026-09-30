import { Search } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { KnowledgeCardView } from "@/components/knowledge/KnowledgeCard";
import { SubmitForm } from "@/components/knowledge/SubmitForm";
import { Empty, inputClass, PageHeader, TabLinks } from "@/components/ui";
import { api } from "@/lib/api.server";
import type { KnowledgeFacets, KnowledgePage } from "@/lib/types";
import { isAdmin } from "@/lib/viewer";

export const metadata: Metadata = {
  title: "知识",
  description: "电力基建知识库：从公众号与专业网站精选的原理、工艺、规范、方案与案例，AI 提炼要点。",
};

type SP = { domain?: string; ktype?: string; q?: string; sort?: string; status?: string; offset?: string };
const PAGE = 20;
const ADMIN_STATUS = [
  ["", "已展示"],
  ["new", "待处理"],
  ["failed", "失败"],
  ["rejected", "未通过"],
  ["duplicate", "重复"],
  ["hidden", "已隐藏"],
] as const;

export default async function KnowledgePageView({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const admin = await isAdmin();
  const offset = Math.max(0, Number(sp.offset ?? 0) || 0);
  const sort = sp.sort === "recent" ? "recent" : "score";
  const status = admin ? (sp.status ?? "") : "";
  const [facets, page] = await Promise.all([
    api<KnowledgeFacets>("/knowledge/facets"),
    api<KnowledgePage>("/knowledge", {
      domain: sp.domain, ktype: sp.ktype, q: sp.q, sort, status: status || undefined, offset, limit: PAGE,
    }),
  ]);
  /** 在当前筛选基础上改一个参数（翻页以外的改动都回到第一页）。 */
  const href = (patch: Partial<SP>) => {
    const p = new URLSearchParams(
      Object.entries({ ...sp, offset: undefined, ...patch }).filter((e): e is [string, string] => !!e[1]),
    );
    const s = p.toString();
    return s ? `/knowledge?${s}` : "/knowledge";
  };
  const filtered = Boolean(sp.domain || sp.ktype || sp.q);

  return (
    <>
      <PageHeader
        title="电力基建知识库"
        desc={`从公众号与专业网站精选的原理、工艺、规范、方案与案例，AI 提炼要点，涉及的标准编号已回原文核对 · 共 ${facets.total} 篇`}
      />
      {admin ? (
        <>
          <SubmitForm />
          <TabLinks
            active={status}
            tabs={ADMIN_STATUS.map(([key, label]) => ({
              key,
              href: href({ status: key || undefined }),
              label: (
                <>
                  {label}
                  <span className="ml-1 text-[11px] opacity-60">{facets.status[key || "analyzed"] ?? 0}</span>
                </>
              ),
            }))}
          />
        </>
      ) : null}

      <div className="mb-4 space-y-3 rounded-lg border border-line bg-surface p-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="w-10 shrink-0 text-xs text-muted">专业</span>
          <FilterChip href={href({ domain: undefined })} active={!sp.domain} label="全部" />
          {facets.domains
            .filter((d) => d.count > 0 || d.key === sp.domain)
            .map((d) => (
              <FilterChip key={d.key} href={href({ domain: d.key })} active={sp.domain === d.key} label={d.label} count={d.count} />
            ))}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="w-10 shrink-0 text-xs text-muted">类型</span>
          <FilterChip href={href({ ktype: undefined })} active={!sp.ktype} label="全部" />
          {facets.types
            .filter((t) => t.count > 0 || t.key === sp.ktype)
            .map((t) => (
              <FilterChip key={t.key} href={href({ ktype: t.key })} active={sp.ktype === t.key} label={t.label} count={t.count} />
            ))}
        </div>
        <form method="get" action="/knowledge" className="flex flex-wrap items-center gap-2">
          {Object.entries({ domain: sp.domain, ktype: sp.ktype, status: status || undefined }).map(([k, v]) =>
            v ? <input key={k} type="hidden" name={k} value={v} /> : null,
          )}
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input name="q" defaultValue={sp.q} placeholder="搜标题、要点、标签，如「接地电阻」「GIS」" className={`${inputClass} pl-8`} />
          </div>
          <input type="hidden" name="sort" value={sort} />
          <div className="flex items-center gap-1 text-sm">
            <Link href={href({ sort: undefined })} className={sort === "score" ? "font-medium text-ink" : "text-muted hover:text-ink"}>
              质量优先
            </Link>
            <span className="text-line">|</span>
            <Link href={href({ sort: "recent" })} className={sort === "recent" ? "font-medium text-ink" : "text-muted hover:text-ink"}>
              最新收录
            </Link>
          </div>
        </form>
      </div>

      {page.items.length === 0 ? (
        <Empty title={filtered ? "没有符合条件的文章" : status ? "这里是空的" : "知识库还是空的"}>
          {filtered ? (
            <Link href="/knowledge" className="text-accent hover:underline">
              清除筛选
            </Link>
          ) : admin && !status ? (
            "在上面粘贴一篇公众号文章链接，开始沉淀第一篇知识。"
          ) : (
            "陆续收录中。"
          )}
        </Empty>
      ) : (
        <>
          <div className="divide-y divide-line">
            {page.items.map((k) => (
              <KnowledgeCardView key={k.id} k={k} />
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-muted">
              第 {offset + 1}–{offset + page.items.length} 篇，共 {page.total} 篇
            </span>
            <div className="flex gap-2">
              {offset > 0 ? (
                <Link href={href({ offset: offset > PAGE ? String(offset - PAGE) : undefined })} className="rounded-md border border-line px-3 py-1.5 hover:bg-surface-2">
                  上一页
                </Link>
              ) : null}
              {offset + PAGE < page.total ? (
                <Link href={href({ offset: String(offset + PAGE) })} className="rounded-md border border-line px-3 py-1.5 hover:bg-surface-2">
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

function FilterChip({ href, active, label, count }: { href: string; active: boolean; label: string; count?: number }) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={active ? "page" : undefined}
      className={
        active
          ? "rounded-full bg-ink px-2.5 py-1 text-xs text-bg"
          : "rounded-full px-2.5 py-1 text-xs text-ink-2 hover:bg-surface-2"
      }
    >
      {label}
      {count !== undefined ? <span className="ml-1 opacity-60">{count}</span> : null}
    </Link>
  );
}
