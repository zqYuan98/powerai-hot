"use client";

import { Zap } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { cn } from "@/lib/cn";

import { MoreMenu } from "./MoreMenu";
import { isActive, NAV } from "./nav";
import { SearchBox } from "./SearchBox";
import { ThemeToggle } from "./ThemeToggle";

export function TopNav() {
  const pathname = usePathname();
  if (pathname.startsWith("/login")) return null;
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md transition-colors">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="group flex shrink-0 items-center gap-2 font-semibold text-ink">
          <span className="flex size-7 items-center justify-center rounded-lg bg-accent-soft text-accent transition group-hover:scale-105">
            <Zap className="size-4" aria-hidden />
          </span>
          <span className="hidden font-bold tracking-tight sm:inline">电力基建情报站</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="主导航">
          {NAV.map((n) => {
            const active = isActive(pathname, n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative rounded-md px-3 py-1.5 text-sm transition-all duration-150",
                  active
                    ? "font-semibold text-ink bg-surface shadow-xs"
                    : "text-muted hover:bg-surface-2/70 hover:text-ink",
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Suspense>
            <SearchBox />
          </Suspense>
          <ThemeToggle />
          <MoreMenu />
        </div>
      </div>
    </header>
  );
}
