import type { ReactNode } from "react";

import { SettingsTabs } from "@/components/settings/SettingsTabs";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <h1 className="mb-3 text-xl font-semibold tracking-tight text-ink">设置</h1>
      <SettingsTabs />
      {children}
    </>
  );
}
