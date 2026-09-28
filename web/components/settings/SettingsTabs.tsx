"use client";

import { usePathname } from "next/navigation";

import { TabLinks } from "@/components/ui";

const TABS = [
  { key: "/settings", href: "/settings", label: "信源与流水线" },
  { key: "/settings/watch", href: "/settings/watch", label: "订阅推送" },
  { key: "/settings/tuning", href: "/settings/tuning", label: "画像与打分" },
  { key: "/settings/usage", href: "/settings/usage", label: "模型用量" },
  { key: "/settings/jobs", href: "/settings/jobs", label: "任务队列" },
];

export function SettingsTabs() {
  return <TabLinks tabs={TABS} active={usePathname()} />;
}
