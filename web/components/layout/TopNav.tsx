"use client";

import { Zap } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { cn } from "@/lib/cn";

import { isActive, NAV } from "./nav";
import { SearchBox } from "./SearchBox";
import { ThemeToggle } from "./ThemeToggle";

export function TopNav() {
  const pathname = usePathname();
  if (pathname.startsWith("/login")) return null;
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <Link href="/" className="flex shrink-0 items-center gap-1.5 font-semibold text-ink">
          <Zap className="size-5 text-accent" aria-hidden />
          <span className="hidden sm:inline">电力基建情报站</span>
        </Link>
        <nav className="hidden items-center gap-0.5 md:flex" aria-label="主导航">
          {NAV.slice(0, 6).map((n) => (
            <Link
              key={n.href}
              href={n.href}
              aria-current={isActive(pathname, n.href) ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-sm transition",
                isActive(pathname, n.href) ? "font-medium text-ink" : "text-muted hover:text-ink",
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <Suspense>
            <SearchBox />
          </Suspense>
          <ThemeToggle />
          <Link
            href="/settings"
            className={cn(
              "hidden rounded-md px-2.5 py-1.5 text-sm md:block",
              isActive(pathname, "/settings") ? "font-medium text-ink" : "text-muted hover:text-ink",
            )}
          >
            设置
          </Link>
        </div>
      </div>
    </header>
  );
}
