"use client";

import { LogOut } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui";
import { send } from "@/lib/api.client";

export function LogoutButton() {
  const [busy, setBusy] = useState(false);
  return (
    <Button
      variant="ghost"
      className="h-8"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await send("/auth/logout", { body: {} });
        } finally {
          // 整页跳转，丢掉所有带管理员身份渲染的内容
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          location.href = "/";
        }
      }}
    >
      <LogOut className="size-4" aria-hidden />
      退出登录
    </Button>
  );
}
