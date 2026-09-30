import type { Metadata } from "next";

import { FeedbackStatusButton } from "@/components/settings/FeedbackStatusButton";
import { Card, Empty, TabLinks } from "@/components/ui";
import { api } from "@/lib/api.server";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import type { FeedbackOut } from "@/lib/types";

export const metadata: Metadata = { title: "访客反馈" };

/** 只把站内路径或 http(s) 地址渲染成链接，其余当纯文本（防 javascript: 之类）。 */
function PageLink({ url }: { url: string }) {
  const safe = /^\/(?!\/)/.test(url) || /^https?:\/\//i.test(url);
  return safe ? (
    <a href={url} target="_blank" rel="noopener noreferrer" className="break-all text-accent hover:underline">
      {url}
    </a>
  ) : (
    <span className="break-all">{url}</span>
  );
}

export default async function FeedbackAdminPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const raw = (await searchParams).status;
  const status = raw === "done" || raw === "all" ? raw : "new";
  const rows = await api<FeedbackOut[]>("/feedback", { status: status === "all" ? undefined : status, limit: 200 });
  return (
    <>
      <TabLinks
        active={status}
        tabs={[
          { key: "new", href: "/settings/feedback", label: "待处理" },
          { key: "done", href: "/settings/feedback?status=done", label: "已处理" },
          { key: "all", href: "/settings/feedback?status=all", label: "全部" },
        ]}
      />
      {rows.length === 0 ? (
        <Empty title={status === "new" ? "没有待处理的反馈" : "没有反馈"}>访客在「反馈」页提交后会出现在这里，配置了飞书时同时推送。</Empty>
      ) : (
        <div className="space-y-3">
          {rows.map((f) => (
            <Card key={f.id} className={cn("p-4", f.status === "done" && "opacity-70")}>
              <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                <span className="font-mono text-ink-2">#{f.id}</span>
                <span>{formatDateTime(f.created_at)}</span>
                {f.contact ? <span className="text-ink-2">联系方式：{f.contact}</span> : null}
                <span className="ml-auto">
                  <FeedbackStatusButton id={f.id} status={f.status} />
                </span>
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink">{f.content}</p>
              <div className="mt-2 space-y-0.5 text-xs text-muted">
                {f.page_url ? (
                  <p>
                    来自页面：<PageLink url={f.page_url} />
                  </p>
                ) : null}
                <p className="truncate" title={f.user_agent ?? undefined}>
                  {f.ip ?? "未知 IP"} · {f.user_agent ?? "未知浏览器"}
                </p>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
