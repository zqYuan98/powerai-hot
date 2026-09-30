import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { LogoutButton } from "@/components/settings/LogoutButton";
import { SettingsTabs } from "@/components/settings/SettingsTabs";
import { isAdmin } from "@/lib/viewer";

export const metadata: Metadata = { robots: { index: false, follow: false } };

/** 后台只对管理员开放；导航里不出现入口，访客直接访问会被带到登录页。 */
export default async function SettingsLayout({ children }: { children: ReactNode }) {
  if (!(await isAdmin())) redirect("/login?next=/settings");
  return (
    <>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight text-ink">后台</h1>
        <LogoutButton />
      </div>
      <SettingsTabs />
      {children}
    </>
  );
}
