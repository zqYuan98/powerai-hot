import type { Metadata } from "next";

import { WatchRules } from "@/components/settings/WatchRules";
import { api } from "@/lib/api.server";
import type { Meta, WatchRuleOut } from "@/lib/types";

export const metadata: Metadata = { title: "订阅推送" };

export default async function WatchPage() {
  const [rules, meta] = await Promise.all([api<WatchRuleOut[]>("/watch-rules"), api<Meta>("/meta")]);
  return (
    <>
      <p className="mb-4 text-sm text-muted">
        精选条目或匹配度高的商机命中任一规则时推送到飞书（每条只推一次）；关注/跟进中的商机在截止前 3 天提醒。
        {meta.push_enabled ? "" : " 当前未配置 FEISHU_WEBHOOK_URL，规则会保存但不会推送。"}
      </p>
      <WatchRules initial={rules} />
    </>
  );
}
