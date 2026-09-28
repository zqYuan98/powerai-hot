"use client";

import { Button, Empty } from "@/components/ui";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <Empty title="页面加载失败">
      <p className="mb-3">{error.message.includes("fetch") ? "后端服务暂时不可用，请稍后再试。" : error.message}</p>
      <Button onClick={reset}>重试</Button>
    </Empty>
  );
}
