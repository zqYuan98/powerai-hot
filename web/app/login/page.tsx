"use client";

import { Zap } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button, inputClass } from "@/components/ui";
import { send } from "@/lib/api.client";

function LoginForm() {
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await send("/auth/login", { body: { password } });
      router.replace(next?.startsWith("/") && !next.startsWith("//") ? next : "/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="w-full max-w-xs space-y-3">
      <div className="mb-6 flex items-center justify-center gap-2 text-lg font-semibold text-ink">
        <Zap className="size-6 text-accent" aria-hidden />
        电力基建情报站
      </div>
      <input
        type="password"
        autoFocus
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="访问口令"
        aria-label="访问口令"
        className={inputClass}
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Button type="submit" variant="primary" className="w-full" disabled={busy || !password}>
        {busy ? "登录中…" : "进入"}
      </Button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-[70dvh] items-center justify-center">
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
