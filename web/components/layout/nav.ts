import { Bookmark, CalendarDays, Flame, Layers, Newspaper, Settings, Target } from "lucide-react";

export const NAV = [
  { href: "/", label: "精选", icon: Newspaper },
  { href: "/leads", label: "商机", icon: Target },
  { href: "/hot", label: "热点", icon: Flame },
  { href: "/daily", label: "日报", icon: CalendarDays },
  { href: "/all", label: "全部", icon: Layers },
  { href: "/starred", label: "收藏", icon: Bookmark },
  { href: "/settings", label: "设置", icon: Settings },
] as const;

export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/" || pathname.startsWith("/items");
  if (href === "/hot" && pathname.startsWith("/stories")) return true;
  return pathname === href || pathname.startsWith(`${href}/`);
}
