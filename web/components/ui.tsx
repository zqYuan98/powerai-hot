import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Badge({ className, ...props }: ComponentProps<"span">) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded px-1.5 py-px text-xs font-medium whitespace-nowrap", className)}
      {...props}
    />
  );
}

const BUTTON = {
  primary: "bg-accent text-white hover:opacity-90",
  secondary: "border border-line bg-surface text-ink hover:bg-surface-2",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
  danger: "border border-line bg-surface text-danger hover:bg-danger-soft",
} as const;

export function Button({
  variant = "secondary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: keyof typeof BUTTON }) {
  return (
    <button
      className={cn(
        "inline-flex h-9 items-center justify-center gap-1.5 rounded-md px-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("rounded-lg border border-line bg-surface shadow-card", className)} {...props} />;
}

export function PageHeader({ title, desc, children }: { title: string; desc?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {desc ? <p className="mt-1 text-sm text-muted">{desc}</p> : null}
      </div>
      {children}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-6 py-14 text-center">
      <p className="font-medium text-ink-2">{title}</p>
      {children ? <div className="mt-2 text-sm text-muted">{children}</div> : null}
    </div>
  );
}

/** 横向滚动的筛选标签（URL 驱动，可分享、可后退）。 */
export function TabLinks({ tabs, active }: { tabs: { href: string; label: ReactNode; key: string }[]; active: string }) {
  return (
    <nav className="scrollbar-none -mx-4 mb-4 flex gap-1 overflow-x-auto px-4" aria-label="筛选">
      {tabs.map((t) => (
        <Link
          key={t.key}
          href={t.href}
          scroll={false}
          aria-current={t.key === active ? "page" : undefined}
          className={cn(
            "flex h-8 shrink-0 items-center rounded-full px-3 text-sm transition",
            t.key === active ? "bg-ink text-bg" : "text-ink-2 hover:bg-surface-2",
          )}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

export function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={cn("flex flex-col gap-1 text-sm", className)}>
      <span className="text-xs font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "h-9 w-full rounded-md border border-line bg-surface px-2.5 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none";

/** 阅读类页面（关于、接入、更新日志、反馈）：正文 + 桌面端右侧栏。 */
export function ReadingLayout({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div className="min-w-0 max-w-3xl">{children}</div>
      {aside ? <aside className="space-y-4">{aside}</aside> : null}
    </div>
  );
}

export function AsideCard({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("p-4", className)}>
      <h2 className="mb-2 text-sm font-semibold text-ink">{title}</h2>
      {children}
    </Card>
  );
}
