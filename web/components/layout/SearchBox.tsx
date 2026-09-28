"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/** 顶部搜索：回车跳转 /search?q=，按「/」聚焦。 */
export function SearchBox() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = useState(pathname === "/search" ? (params.get("q") ?? "") : "");
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(tag)) {
        e.preventDefault();
        ref.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        const v = q.trim();
        if (v) router.push(`/search?q=${encodeURIComponent(v)}`);
      }}
      className="relative"
    >
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        ref={ref}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="搜索项目、业主、关键词"
        aria-label="搜索"
        className="h-9 w-44 rounded-md border border-line bg-surface pr-7 pl-8 text-sm text-ink transition-[width] placeholder:text-muted focus:w-56 focus:border-accent focus:outline-none sm:w-56 sm:focus:w-72"
      />
      <kbd className="pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 rounded border border-line px-1 text-[10px] text-muted sm:block">
        /
      </kbd>
    </form>
  );
}
