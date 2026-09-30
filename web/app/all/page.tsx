import type { Metadata } from "next";

import { ChannelTabs } from "@/components/feed/ChannelTabs";
import { FeedList } from "@/components/feed/FeedList";
import { PageHeader, TabLinks } from "@/components/ui";
import { api } from "@/lib/api.server";
import type { ItemCard, Page } from "@/lib/types";
import { isAdmin } from "@/lib/viewer";

export const metadata: Metadata = { title: "全部" };

export default async function AllPage({
  searchParams,
}: {
  searchParams: Promise<{ channel?: string; view?: string }>;
}) {
  const { channel = "", view: rawView } = await searchParams;
  const admin = await isAdmin();
  // 被淘汰/失败的条目只给管理员回溯误杀
  const view = rawView === "screened" && admin ? "screened" : "all";
  const query = { view, ...(channel ? { channel } : {}) };
  const page = await api<Page<ItemCard>>("/items", { ...query, limit: 30 });

  return (
    <>
      <PageHeader
        title="全部"
        desc={view === "all" ? "所有完成精读的条目，含未进精选的低分项" : "被初筛淘汰或处理失败的条目，用于回溯误杀"}
      />
      {admin ? (
        <TabLinks
          active={view}
          tabs={[
            { key: "all", href: "/all", label: "已精读" },
            { key: "screened", href: "/all?view=screened", label: "已淘汰 / 失败" },
          ]}
        />
      ) : null}
      {view === "all" ? <ChannelTabs base="/all" active={channel} /> : null}
      <FeedList key={`${view}-${channel}`} initial={page} query={query} />
    </>
  );
}
