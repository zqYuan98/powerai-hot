"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui";
import { send } from "@/lib/api.client";
import type { FeedbackOut } from "@/lib/types";

export function FeedbackStatusButton({ id, status }: { id: number; status: FeedbackOut["status"] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const next = status === "new" ? "done" : "new";
  return (
    <Button
      className="h-7 px-2 text-xs"
      variant={status === "new" ? "primary" : "secondary"}
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await send(`/feedback/${id}`, { method: "PATCH", body: { status: next } });
          router.refresh();
        } finally {
          setBusy(false);
        }
      }}
    >
      {status === "new" ? "标为已处理" : "重新打开"}
    </Button>
  );
}
