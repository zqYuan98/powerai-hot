"use client";

import { MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/cn";

import { isActive, NAV } from "./nav";

const PRIMARY_HREFS = ["/", "/leads", "/daily"];
const PRIMARY = NAV.filter((n) => PRIMARY_HREFS.includes(n.href));
const MORE = NAV.filter((n) => !PRIMARY_HREFS.includes(n.href));

/** 移动端底部导航：精选 · 商机 · 日报 · 更多（抽屉）。 */
export function MobileNav() {
  const pathname = usePathname();
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === pathname; // 路由变化后自动收起
  if (pathname.startsWith("/login")) return null;
  const moreActive = MORE.some((n) => isActive(pathname, n.href));

  return (
    <>
      {open ? (
        <>
          <div className="fixed inset-0 z-40 bg-black/30 md:hidden" onClick={() => setOpenAt(null)} aria-hidden />
          <div
            role="dialog"
            aria-label="更多"
            className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-50 rounded-t-xl border-t border-line bg-surface p-3 md:hidden"
          >
            <div className="grid grid-cols-4 gap-2">
              {MORE.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex flex-col items-center gap-1 rounded-lg py-3 text-xs",
                    isActive(pathname, href) ? "bg-accent-soft text-accent" : "text-ink-2",
                  )}
                >
                  <Icon className="size-5" aria-hidden />
                  {label}
                </Link>
              ))}
            </div>
          </div>
        </>
      ) : null}
      <nav
        aria-label="底部导航"
        className="fixed inset-x-0 bottom-0 z-50 flex border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        {PRIMARY.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            aria-current={isActive(pathname, href) ? "page" : undefined}
            className={cn(
              "flex h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[11px]",
              isActive(pathname, href) ? "text-accent" : "text-muted",
            )}
          >
            <Icon className="size-5" aria-hidden />
            {label}
          </Link>
        ))}
        <button
          type="button"
          onClick={() => setOpenAt(open ? null : pathname)}
          aria-expanded={open}
          className={cn(
            "flex h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[11px]",
            moreActive || open ? "text-accent" : "text-muted",
          )}
        >
          <MoreHorizontal className="size-5" aria-hidden />
          更多
        </button>
      </nav>
    </>
  );
}
