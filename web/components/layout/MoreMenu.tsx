"use client";

import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import { useChangelogUnseen } from "@/lib/local";

import { ADMIN_LINK, isActive, MORE_LINKS } from "./nav";
import { useIsAdmin } from "./ViewerProvider";

export function Dot({ className }: { className?: string }) {
  return <span className={cn("size-1.5 rounded-full bg-danger", className)} aria-label="有更新" />;
}

type NavLink = (typeof MORE_LINKS)[number] | typeof ADMIN_LINK;

function MenuLink({ link: { href, label, icon: Icon }, active, dot }: { link: NavLink; active: boolean; dot: boolean }) {
  return (
    <Link
      href={href}
      role="menuitem"
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm",
        active ? "bg-surface-2 font-medium text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
      )}
    >
      <Icon className="size-4 text-muted" aria-hidden />
      <span className="flex-1">{label}</span>
      {dot ? <Dot /> : null}
    </Link>
  );
}

/** 桌面端顶栏「更多」下拉：Agent 接入、关于、更新日志、反馈（管理员另有后台）。 */
export function MoreMenu() {
  const pathname = usePathname();
  const admin = useIsAdmin();
  const unseen = useChangelogUnseen();
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === pathname; // 路由变化后自动收起
  const ref = useRef<HTMLDivElement>(null);
  const active = [...MORE_LINKS, ADMIN_LINK].some((l) => isActive(pathname, l.href));

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpenAt(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenAt(null);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative hidden md:block">
      <button
        type="button"
        onClick={() => setOpenAt(open ? null : pathname)}
        aria-expanded={open}
        aria-haspopup="menu"
        className={cn(
          "flex h-9 items-center gap-1 rounded-md px-2.5 text-sm transition",
          active || open ? "font-medium text-ink" : "text-muted hover:text-ink",
        )}
      >
        更多
        {unseen ? <Dot /> : null}
        <ChevronDown className={cn("size-3.5 transition", open && "rotate-180")} aria-hidden />
      </button>
      {open ? (
        <div role="menu" className="absolute right-0 z-40 mt-1 w-44 rounded-lg border border-line bg-surface p-1 shadow-card">
          {MORE_LINKS.map((l) => (
            <MenuLink key={l.href} link={l} active={isActive(pathname, l.href)} dot={l.changelog && unseen} />
          ))}
          {admin ? (
            <>
              <div className="my-1 border-t border-line" role="separator" />
              <MenuLink link={ADMIN_LINK} active={isActive(pathname, ADMIN_LINK.href)} dot={false} />
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
